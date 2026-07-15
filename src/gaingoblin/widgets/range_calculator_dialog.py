from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QCloseEvent, QResizeEvent, QShowEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gaingoblin.calculations import to_decimal
from gaingoblin.market_data.cache import MarketDataCache
from gaingoblin.market_data.errors import (
    MarketDataDisabledError,
    MarketDataError,
    MissingApiKeyError,
)
from gaingoblin.market_data.historical_range import calculate_historical_range_metrics
from gaingoblin.market_data.models import HistoricalRangeMetrics, MarketDataQuote
from gaingoblin.market_data.provenance import (
    BADGE_TOOLTIPS,
    ValueOrigin,
    badge_label_for_origin,
    provenance_line,
    status_badge_for_freshness,
    summary_low_high_phrase,
)
from gaingoblin.market_data.provider_base import MarketDataProvider
from gaingoblin.market_data.providers.alpha_vantage_provider import AlphaVantageProvider
from gaingoblin.market_data.providers.mock_provider import MockProvider
from gaingoblin.market_data.secret_store import MemorySecretStore, SecretStore
from gaingoblin.market_data.settings import MarketDataSettings, MarketDataSettingsStore
from gaingoblin.models import Holding
from gaingoblin.quote_comparison import calculate_quote_comparison
from gaingoblin.range_calculator import (
    RangeScenarioInput,
    RangeScenarioResult,
    calculate_range_scenario,
)
from gaingoblin.widgets.dialog_utils import center_and_clamp_dialog
from gaingoblin.widgets.holding_dialog import MoneyEdit
from gaingoblin.widgets.market_data_settings_dialog import (
    ALPHA_VANTAGE,
    MarketDataSettingsDialog,
)

logger = logging.getLogger(__name__)

MARKET_DATA_WARNING = (
    "Market values may be historical, delayed, end-of-day, or real-time depending on the "
    "provider and account plan. They are not predictions or recommendations."
)


@dataclass(slots=True)
class _FetchRequest:
    symbol: str
    lookback_days: int
    online_enabled: bool
    provider: MarketDataProvider
    quote_cache_minutes: int


@dataclass(slots=True)
class _FetchOutcome:
    metrics: HistoricalRangeMetrics | None = None
    metrics_from_cache: bool = False
    quote: MarketDataQuote | None = None
    quote_from_cache: bool = False
    error_message: str | None = None
    elapsed_seconds: float = 0.0
    provider_name: str = ""
    symbol: str = ""
    lookback_days: int = 0


class _FetchWorker(QObject):
    finished = Signal(object)

    def __init__(self, dialog: RangeCalculatorDialog, request: _FetchRequest) -> None:
        super().__init__()
        self._dialog = dialog
        self._request = request

    def run(self) -> None:
        """Fetch market data on the worker thread."""
        self.finished.emit(self._dialog._execute_fetch(self._request))


class RangeCalculatorDialog(QDialog):
    calculation_succeeded = Signal()
    validation_failed = Signal()
    fetch_started = Signal()
    fetch_succeeded = Signal()
    fetch_failed = Signal()

    RESULT_FIELDS = [
        ("entry_cost", "Entry Cost"),
        ("low_value", "Value at Average Low"),
        ("high_value", "Value at Average High"),
        ("low_profit", "Possible Loss at Low"),
        ("high_profit", "Possible Gain at High"),
        ("low_roi_percent", "ROI at Low"),
        ("high_roi_percent", "ROI at High"),
        ("break_even_price", "Break-Even Price"),
        ("price_spread", "Price Spread"),
        ("spread_percent", "Spread %"),
        ("gain_per_share_at_high", "Gain/Loss per Share at High"),
        ("loss_per_share_at_low", "Gain/Loss per Share at Low"),
        ("goblin_note", "Goblin Note"),
    ]

    LOOKBACK_WINDOWS = [
        ("20 trading days", 20),
        ("50 trading days", 50),
        ("90 trading days", 90),
        ("180 trading days", 180),
        ("252 trading days / 1 year", 252),
    ]

    PROVIDER_CLASSES = {
        "Mock": MockProvider,
        ALPHA_VANTAGE: AlphaVantageProvider,
    }

    SETUP_ONBOARDING_MESSAGE = (
        "Market Data Scout needs a quick setup first. "
        "Open Market Data Settings to save an Alpha Vantage API key and enable online data. "
        "Your calculator numbers stay exactly as you left them."
    )

    _PROVENANCE_FIELDS = (
        "planned_buy_price",
        "average_low_price",
        "average_high_price",
        "current_price",
        "week_52_low",
        "week_52_high",
        "average_volume",
    )

    def __init__(
        self,
        selected_holding: Holding | None = None,
        parent: QWidget | None = None,
        market_data_provider: MarketDataProvider | None = None,
        market_data_cache: MarketDataCache | None = None,
        settings_store: MarketDataSettingsStore | None = None,
        secret_store: SecretStore | None = None,
    ) -> None:
        super().__init__(parent)
        self.selected_holding = selected_holding
        self.injected_provider = market_data_provider
        self.settings_store = settings_store or MarketDataSettingsStore.default()
        if secret_store is not None:
            self.secret_store = secret_store
        else:
            self.secret_store = (
                getattr(self.settings_store, "secret_store", None) or MemorySecretStore()
            )
            if getattr(self.settings_store, "secret_store", None) is None:
                self.settings_store.secret_store = self.secret_store

        self.settings = self.settings_store.load()
        if self.injected_provider is not None:
            self.settings = MarketDataSettings(
                market_data_enabled=True,
                selected_provider=self.injected_provider.provider_name,
                cache_duration_minutes=self.settings.cache_duration_minutes,
            )
        self.market_data_cache = market_data_cache or MarketDataCache.default()
        self.market_data_cache.historical_ttl = timedelta(hours=24)
        self.market_data_cache.quote_ttl = timedelta(minutes=self.settings.cache_duration_minutes)

        self.last_result: RangeScenarioResult | None = None
        self.last_metrics: HistoricalRangeMetrics | None = None
        self.last_quote: MarketDataQuote | None = None
        self._fetch_thread: QThread | None = None
        self._fetch_worker: _FetchWorker | None = None
        self._fetch_in_progress = False
        self._setup_offer_pending = False
        self._programmatic_field_update = False
        self._layout_mode = ""
        self._last_metrics_from_cache = False
        self._last_quote_from_cache = False
        self._planned_buy_from_holding = False
        self._field_origins = {
            field_key: ValueOrigin.MANUAL for field_key in self._PROVENANCE_FIELDS
        }
        self._field_freshness = {field_key: "" for field_key in self._PROVENANCE_FIELDS}
        self._field_badges: dict[str, QLabel] = {}

        self.setWindowTitle("Range Profit Calculator")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.resize(1000, 700)
        self.setMinimumSize(700, 520)

        intro = QLabel(
            "Range Calculator uses only numbers shown in editable fields. "
            "It does not place trades or direct trading choices."
        )
        intro.setObjectName("HelperText")
        intro.setWordWrap(True)

        self.status_label = QLabel(
            "Give me the low, give me the high, give me the shares - I'll count the possible loot."
        )
        self.status_label.setObjectName("HelperText")
        self.status_label.setWordWrap(True)

        self._create_input_widgets()
        self.input_panel = self._build_input_panel()
        self.scout_panel = self._build_scout_panel()
        self.quote_panel = self._build_quote_panel()
        self.history_panel = self._build_history_panel()
        self.market_column = self._build_market_column()
        self.results_panel = self._build_results_panel()
        self.comparison_panel = self._build_comparison_panel()

        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.addWidget(self.input_panel)
        self.splitter.addWidget(self.market_column)
        self.splitter.setStretchFactor(0, 1)
        self.splitter.setStretchFactor(1, 1)

        results_section = QWidget()
        results_layout = QVBoxLayout(results_section)
        results_layout.setContentsMargins(0, 0, 0, 0)
        results_layout.addWidget(self.comparison_panel)
        results_layout.addWidget(self.results_panel)

        form_shell = QWidget()
        form_shell_layout = QVBoxLayout(form_shell)
        form_shell_layout.addWidget(intro)
        form_shell_layout.addWidget(self.status_label)
        form_shell_layout.addWidget(self.splitter)
        form_shell_layout.addWidget(results_section)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(form_shell)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.calculate_button = self.buttons.addButton(
            "Calculate", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.copy_button = self.buttons.addButton(
            "Copy Result Summary", QDialogButtonBox.ButtonRole.ActionRole
        )
        self.copy_button.setEnabled(False)
        self.calculate_button.clicked.connect(self.calculate_current_scenario)
        self.copy_button.clicked.connect(self.copy_result_summary)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.buttons)

        self._connect_field_handlers()
        self._refresh_setup_labels()
        self._refresh_badges()
        self._update_market_cards(None, False, None, False)
        self._update_quote_comparison()
        self._rebuild_content_layout()

    def _create_input_widgets(self) -> None:
        """Create editable scenario fields and their load action."""
        self.symbol_name = QLineEdit()
        self.symbol_name.setPlaceholderText("ORC")
        self.shares = MoneyEdit(6)
        self.planned_buy_price = MoneyEdit(4)
        self.average_low_price = MoneyEdit(4)
        self.average_high_price = MoneyEdit(4)
        self.buy_fees = MoneyEdit(4)
        self.sell_fees = MoneyEdit(4)
        self.week_52_low = MoneyEdit(4)
        self.week_52_high = MoneyEdit(4)
        self.current_price = MoneyEdit(4)
        self.average_volume = QLineEdit()
        self.average_volume.setPlaceholderText("Optional")
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(76)
        self.notes.setMaximumHeight(130)
        self.load_selected_button = QPushButton("Load Selected Holding")
        self.load_selected_button.setEnabled(self.selected_holding is not None)
        self.load_selected_button.clicked.connect(self.load_selected_holding)

    def _build_input_panel(self) -> QFrame:
        """Build the left scenario-input column."""
        panel = QFrame()
        panel.setObjectName("RangeResultsPanel")
        layout = QVBoxLayout(panel)
        title = QLabel("Scenario Inputs")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)
        layout.addWidget(self.load_selected_button, alignment=Qt.AlignmentFlag.AlignLeft)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        form.addRow("Ticker / Symbol", self.symbol_name)
        form.addRow("Shares", self.shares)
        form.addRow(
            "Planned Buy Price",
            self._make_field_row(self.planned_buy_price, "planned_buy_price"),
        )
        form.addRow(
            "Average Low Price",
            self._make_field_row(self.average_low_price, "average_low_price"),
        )
        form.addRow(
            "Average High Price",
            self._make_field_row(self.average_high_price, "average_high_price"),
        )
        form.addRow("Buy Fees", self.buy_fees)
        form.addRow("Sell Fees", self.sell_fees)
        form.addRow(
            "Optional 52-Week Low",
            self._make_field_row(self.week_52_low, "week_52_low"),
        )
        form.addRow(
            "Optional 52-Week High",
            self._make_field_row(self.week_52_high, "week_52_high"),
        )
        form.addRow(
            "Optional Current Price",
            self._make_field_row(self.current_price, "current_price"),
        )
        form.addRow(
            "Optional Average Volume",
            self._make_field_row(self.average_volume, "average_volume"),
        )
        form.addRow("Notes", self.notes)
        layout.addWidget(form_host)
        layout.addStretch(1)
        return panel

    def _build_scout_panel(self) -> QFrame:
        """Build setup, lookback, and fetch controls."""
        panel = QFrame()
        panel.setObjectName("RangeResultsPanel")
        form = QFormLayout(panel)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.online_enabled = QCheckBox("Enable Market Data Scout")
        self.online_enabled.setChecked(self.settings.market_data_enabled)
        self.online_enabled.hide()
        self.setup_status_label = QLabel()
        self.setup_status_label.setObjectName("HelperText")
        self.setup_status_label.setWordWrap(True)
        self.provider_value = QLabel()
        self.online_value = QLabel()
        self.lookback_combo = QComboBox()
        for label, value in self.LOOKBACK_WINDOWS:
            self.lookback_combo.addItem(label, value)
        self.lookback_combo.setCurrentIndex(2)

        self.open_settings_button = QPushButton("Open Market Data Settings")
        self.open_settings_button.clicked.connect(self.open_market_data_settings)
        self.fetch_button = QPushButton("Fetch Market Numbers")
        self.fetch_button.clicked.connect(self.start_market_data_fetch)
        self.refresh_button = QPushButton("Refresh Market Data")
        self.refresh_button.clicked.connect(self.start_market_data_fetch)
        self.apply_range_button = QPushButton("Apply Fetched Range")
        self.apply_range_button.setEnabled(False)
        self.apply_range_button.clicked.connect(self.apply_fetched_range)
        self.use_average_button = self.apply_range_button
        self.clear_fetch_button = QPushButton("Clear Fetched Data")
        self.clear_fetch_button.clicked.connect(self.clear_fetched_values)

        self.source_value = QLabel("Not fetched")
        self.source_value.setWordWrap(True)
        self.fetched_value = QLabel("Not fetched")
        self.fetched_value.setWordWrap(True)
        self.freshness_value = QLabel("Quote: NOT FETCHED · History: NOT FETCHED")
        self.freshness_value.setWordWrap(True)
        self.lookback_value = QLabel("Not fetched")
        self.cache_status_value = QLabel("Not fetched")
        self.delay_value = self.freshness_value
        self.market_warning = QLabel(MARKET_DATA_WARNING)
        self.market_warning.setObjectName("HelperText")
        self.market_warning.setWordWrap(True)
        self.historical_warning = self.market_warning

        form.addRow("", QLabel("Market Data Scout"))
        form.addRow("Setup", self.setup_status_label)
        form.addRow("Provider", self.provider_value)
        form.addRow("Online Data", self.online_value)
        form.addRow("Lookback Window", self.lookback_combo)
        form.addRow("Sources", self.source_value)
        form.addRow("Fetched", self.fetched_value)
        form.addRow("Freshness", self.freshness_value)
        form.addRow("Lookback", self.lookback_value)
        form.addRow("Cache", self.cache_status_value)
        form.addRow("", self.open_settings_button)
        form.addRow("", self.fetch_button)
        form.addRow("", self.refresh_button)
        form.addRow("", self.apply_range_button)
        form.addRow("", self.clear_fetch_button)
        form.addRow("", self.market_warning)
        return panel

    def _build_quote_panel(self) -> QFrame:
        """Build the quote preview card."""
        panel = QFrame()
        panel.setObjectName("RangeResultsPanel")
        form = QFormLayout(panel)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        title = QLabel("Latest Quote")
        title.setObjectName("SectionTitle")
        form.addRow("", title)

        self.quote_price_value = self._preview_label()
        self.quote_day_high_value = self._preview_label()
        self.quote_day_low_value = self._preview_label()
        self.quote_previous_close_value = self._preview_label()
        self.quote_volume_value = self._preview_label()
        self.quote_provider_value = self._preview_label()
        self.quote_freshness_badge = self._preview_label()
        self.quote_fetched_value = self._preview_label()
        self.quote_cache_badge = self._preview_label()
        form.addRow("Price", self.quote_price_value)
        form.addRow("Day High", self.quote_day_high_value)
        form.addRow("Day Low", self.quote_day_low_value)
        form.addRow("Previous Close", self.quote_previous_close_value)
        form.addRow("Volume", self.quote_volume_value)
        form.addRow("Provider", self.quote_provider_value)
        form.addRow("Status", self.quote_freshness_badge)
        form.addRow("Fetched", self.quote_fetched_value)
        form.addRow("Cache", self.quote_cache_badge)
        return panel

    def _build_history_panel(self) -> QFrame:
        """Build the historical metrics preview card."""
        panel = QFrame()
        panel.setObjectName("RangeResultsPanel")
        form = QFormLayout(panel)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        title = QLabel("Historical Range")
        title.setObjectName("SectionTitle")
        form.addRow("", title)

        self.history_requested_value = self._preview_label()
        self.history_bars_value = self._preview_label()
        self.history_dates_value = self._preview_label()
        self.history_average_low_value = self._preview_label()
        self.history_average_high_value = self._preview_label()
        self.history_52_low_value = self._preview_label()
        self.history_52_high_value = self._preview_label()
        self.history_average_volume_value = self._preview_label()
        self.history_provider_value = self._preview_label()
        self.history_fetched_value = self._preview_label()
        self.history_cache_badge = self._preview_label()
        self.history_status_badge = self._preview_label()
        self.history_cache_notice = QLabel()
        self.history_cache_notice.setObjectName("HelperText")
        self.history_cache_notice.setWordWrap(True)
        self.history_cache_notice.hide()
        self.history_fewer_bars_notice = QLabel()
        self.history_fewer_bars_notice.setObjectName("HelperText")
        self.history_fewer_bars_notice.setWordWrap(True)
        self.history_fewer_bars_notice.hide()

        form.addRow("Requested Lookback", self.history_requested_value)
        form.addRow("Bars Used", self.history_bars_value)
        form.addRow("Date Range", self.history_dates_value)
        form.addRow("Average Low", self.history_average_low_value)
        form.addRow("Average High", self.history_average_high_value)
        form.addRow("52-Week Low", self.history_52_low_value)
        form.addRow("52-Week High", self.history_52_high_value)
        form.addRow("Average Volume", self.history_average_volume_value)
        form.addRow("Provider", self.history_provider_value)
        form.addRow("Status", self.history_status_badge)
        form.addRow("Fetched", self.history_fetched_value)
        form.addRow("Cache", self.history_cache_badge)
        form.addRow("", self.history_cache_notice)
        form.addRow("", self.history_fewer_bars_notice)
        return panel

    def _build_market_column(self) -> QWidget:
        """Build the right market-data column."""
        column = QWidget()
        layout = QVBoxLayout(column)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.scout_panel)
        layout.addWidget(self.quote_panel)
        layout.addWidget(self.history_panel)
        layout.addStretch(1)
        return column

    def _build_results_panel(self) -> QFrame:
        """Build the scenario results card."""
        panel = QFrame()
        panel.setObjectName("RangeResultsPanel")
        self.result_labels: dict[str, QLabel] = {}
        form = QFormLayout(panel)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        title = QLabel("Scenario Results")
        title.setObjectName("SectionTitle")
        form.addRow("", title)
        for key, label_text in self.RESULT_FIELDS:
            value = self._preview_label("--")
            value.setWordWrap(True)
            self.result_labels[key] = value
            form.addRow(label_text, value)
        return panel

    def _build_comparison_panel(self) -> QFrame:
        """Build the neutral current quote comparison card."""
        panel = QFrame()
        panel.setObjectName("RangeResultsPanel")
        form = QFormLayout(panel)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        title = QLabel("Current Quote Comparison")
        title.setObjectName("SectionTitle")
        form.addRow("", title)
        self.comparison_quote_value = self._preview_label()
        self.comparison_per_share_value = self._preview_label()
        self.comparison_position_value = self._preview_label()
        self.comparison_roi_value = self._preview_label()
        self.comparison_note = QLabel(
            "Neutral comparison of the current quote with the entered plan; "
            "it does not change scenario math."
        )
        self.comparison_note.setObjectName("HelperText")
        self.comparison_note.setWordWrap(True)
        form.addRow("Current Quote", self.comparison_quote_value)
        form.addRow("Per-Share Difference", self.comparison_per_share_value)
        form.addRow("Position Difference", self.comparison_position_value)
        form.addRow("Difference vs Entry", self.comparison_roi_value)
        form.addRow("", self.comparison_note)
        return panel

    @staticmethod
    def _preview_label(text: str = "Unavailable") -> QLabel:
        label = QLabel(text)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        return label

    def _make_field_row(self, widget: QWidget, badge_key: str) -> QWidget:
        """Wrap an editable field with its subtle provenance badge."""
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(widget, 1)
        badge = QLabel()
        badge.setObjectName("HelperText")
        badge.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Preferred)
        self._field_badges[badge_key] = badge
        layout.addWidget(badge)
        return row

    def _connect_field_handlers(self) -> None:
        """Connect provenance and comparison updates to editable fields."""
        for field_key in self._PROVENANCE_FIELDS:
            edit = getattr(self, field_key)
            edit.textChanged.connect(lambda _text, key=field_key: self._on_field_edited(key))
        for edit in (self.shares, self.buy_fees, self.sell_fees):
            edit.textChanged.connect(self._update_quote_comparison)

    def showEvent(self, event: QShowEvent) -> None:
        """Center the dialog and apply its initial responsive orientation."""
        super().showEvent(event)
        self._rebuild_content_layout()
        center_and_clamp_dialog(self, self.parentWidget())

    def resizeEvent(self, event: QResizeEvent) -> None:
        """Switch the splitter orientation at the responsive breakpoint."""
        super().resizeEvent(event)
        self._rebuild_content_layout()

    def closeEvent(self, event: QCloseEvent) -> None:
        """Detach the worker before closing."""
        self._detach_fetch_worker()
        super().closeEvent(event)

    def _rebuild_content_layout(self) -> None:
        """Reorient existing widgets without destroying or recreating them."""
        mode = "wide" if self.width() >= 900 else "narrow"
        if mode == self._layout_mode:
            return
        self._layout_mode = mode
        orientation = Qt.Orientation.Horizontal if mode == "wide" else Qt.Orientation.Vertical
        self.splitter.setOrientation(orientation)
        if mode == "wide":
            self.splitter.setSizes([480, 480])
        else:
            self.splitter.setSizes([420, 620])

    def load_selected_holding(self) -> None:
        """Load compatible scenario values from the selected holding."""
        if self.selected_holding is None:
            return
        holding = self.selected_holding
        self.symbol_name.setText(holding.symbol_name)
        self.shares.setText(str(holding.shares))
        self._set_field_text(
            self.planned_buy_price,
            str(holding.buy_price),
            ValueOrigin.MANUAL,
        )
        self._planned_buy_from_holding = True
        self.buy_fees.setText(str(holding.buy_fees))
        self.sell_fees.setText(str(holding.sell_fees))
        if not self.notes.toPlainText().strip() and holding.notes:
            self.notes.setPlainText(holding.notes)
        self.status_label.setText(
            "Selected holding loaded. Enter average low and high values to calculate the range."
        )
        self._update_quote_comparison()

    def scenario_input(self) -> RangeScenarioInput:
        """Return the scenario represented by the editable fields."""
        return RangeScenarioInput(
            symbol_name=self.symbol_name.text().strip(),
            shares=to_decimal(self.shares.text()),
            planned_buy_price=to_decimal(self.planned_buy_price.text()),
            average_low_price=to_decimal(self.average_low_price.text()),
            average_high_price=to_decimal(self.average_high_price.text()),
            buy_fees=to_decimal(self.buy_fees.text()),
            sell_fees=to_decimal(self.sell_fees.text()),
            notes=self.notes.toPlainText().strip(),
        )

    def calculate_current_scenario(self) -> RangeScenarioResult | None:
        """Calculate and display the current editable scenario."""
        try:
            result = calculate_range_scenario(self.scenario_input())
        except ValueError as exc:
            self.last_result = None
            self.copy_button.setEnabled(False)
            self.status_label.setText(str(exc))
            self._clear_results()
            self._update_quote_comparison()
            self.validation_failed.emit()
            return None

        self.last_result = result
        self._populate_results(result)
        self._update_quote_comparison()
        self.copy_button.setEnabled(True)
        self.status_label.setText("Projected math tallied from your editable range values.")
        self.calculation_succeeded.emit()
        return result

    def fetch_historical_range(self) -> HistoricalRangeMetrics | None:
        """Compatibility wrapper for synchronous market-data fetches."""
        return self.fetch_market_numbers()

    def start_market_data_fetch(self) -> None:
        """Start a background scout request without freezing the UI."""
        if self._fetch_in_progress:
            return
        symbol = self.symbol_name.text().strip().upper()
        if not symbol:
            self.status_label.setText("Enter a ticker or symbol before fetching market numbers.")
            self.fetch_failed.emit()
            return
        if not self._ensure_setup_ready(offer_dialog=True):
            self.fetch_failed.emit()
            return
        try:
            request = self._build_fetch_request()
        except Exception:
            logger.exception("Failed to prepare market-data fetch")
            self.status_label.setText("Market data provider is unavailable.")
            self.fetch_failed.emit()
            return

        self._fetch_in_progress = True
        self._set_fetch_buttons_enabled(False)
        self.status_label.setText("Scouting market trail…")
        self.fetch_started.emit()

        thread = QThread(self)
        worker = _FetchWorker(self, request)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_fetch_worker_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_fetch_thread_finished)
        self._fetch_thread = thread
        self._fetch_worker = worker
        thread.start()

    def fetch_market_numbers(self) -> HistoricalRangeMetrics | None:
        """Synchronously fetch market data, primarily for tests and integrations."""
        self.fetch_started.emit()
        if not self._ensure_setup_ready(offer_dialog=False):
            self.fetch_failed.emit()
            return None
        try:
            request = self._build_fetch_request()
        except Exception:
            logger.exception("Failed to prepare market-data fetch")
            self.status_label.setText("Market data provider is unavailable.")
            self.fetch_failed.emit()
            return None
        return self._apply_fetch_outcome(self._execute_fetch(request))

    def _build_fetch_request(self) -> _FetchRequest:
        return _FetchRequest(
            symbol=self.symbol_name.text().strip().upper(),
            lookback_days=int(self.lookback_combo.currentData() or 90),
            online_enabled=self.online_enabled.isChecked(),
            provider=self._current_provider(),
            quote_cache_minutes=self.settings.cache_duration_minutes,
        )

    def open_market_data_settings(self) -> bool:
        """Open guided Market Data Settings and refresh local labels afterward."""
        if self.injected_provider is not None:
            self.status_label.setText(
                "A test market-data provider is active. Settings dialog is available "
                "for production path only."
            )
            return False
        dialog = MarketDataSettingsDialog(
            parent=self,
            settings_store=self.settings_store,
            secret_store=self.secret_store,
            market_data_cache=self.market_data_cache,
            test_symbol=self.symbol_name.text().strip().upper() or "IBM",
        )
        accepted = dialog.exec() == QDialog.DialogCode.Accepted
        self._reload_settings_from_store()
        self._refresh_setup_labels()
        if accepted:
            self.status_label.setText(
                "Market Data Settings updated. Click Fetch Market Numbers when you are ready."
            )
        return accepted

    def _ensure_setup_ready(self, *, offer_dialog: bool) -> bool:
        ready, reason = self._setup_readiness()
        if ready:
            return True
        self.status_label.setText(reason)
        self._setup_offer_pending = True
        self._refresh_setup_labels()
        if offer_dialog:
            answer = QMessageBox.question(
                self,
                "Market Data Setup Needed",
                f"{self.SETUP_ONBOARDING_MESSAGE}\n\nOpen Market Data Settings now?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            if answer == QMessageBox.StandardButton.Yes:
                self.open_market_data_settings()
        return False

    def _setup_readiness(self) -> tuple[bool, str]:
        if self.injected_provider is not None:
            return True, ""
        self._reload_settings_from_store()
        if not self.settings.market_data_enabled:
            return False, self.SETUP_ONBOARDING_MESSAGE
        provider_name = self._active_provider_name()
        if provider_name not in self.PROVIDER_CLASSES:
            return False, self.SETUP_ONBOARDING_MESSAGE
        provider_class = self.PROVIDER_CLASSES[provider_name]
        if provider_class.requires_api_key and not self.secret_store.get_secret(provider_name):
            return False, self.SETUP_ONBOARDING_MESSAGE
        return True, ""

    def _reload_settings_from_store(self) -> None:
        if self.injected_provider is not None:
            return
        self.settings = self.settings_store.load()
        if self.settings.selected_provider not in self.PROVIDER_CLASSES:
            self.settings = MarketDataSettings(
                market_data_enabled=self.settings.market_data_enabled,
                selected_provider=ALPHA_VANTAGE,
                cache_duration_minutes=self.settings.cache_duration_minutes,
            )
        self.online_enabled.setChecked(self.settings.market_data_enabled)
        self.market_data_cache.quote_ttl = timedelta(minutes=self.settings.cache_duration_minutes)

    def _refresh_setup_labels(self) -> None:
        self.setup_status_label.setText(self._setup_status_text())
        self.provider_value.setText(self._active_provider_name())
        self.online_value.setText(self._online_status_text())

    def _setup_status_text(self) -> str:
        ready, _reason = self._setup_readiness()
        return "Ready" if ready else "Setup needed — open Market Data Settings"

    def _online_status_text(self) -> str:
        return "Enabled" if self.settings.market_data_enabled else "Disabled (default)"

    def _active_provider_name(self) -> str:
        if self.injected_provider is not None:
            return self.injected_provider.provider_name
        name = self.settings.selected_provider
        return name if name in self.PROVIDER_CLASSES else ALPHA_VANTAGE

    def apply_fetched_range(self) -> None:
        """Apply fetched previews to editable fields with explicit provenance."""
        metrics = self.last_metrics
        if metrics is None:
            return
        history_freshness = metrics.freshness_label
        self._set_field_text(
            self.average_low_price,
            self._format_decimal(metrics.average_low, places=4),
            ValueOrigin.FETCHED_HISTORY,
            history_freshness,
        )
        self._set_field_text(
            self.average_high_price,
            self._format_decimal(metrics.average_high, places=4),
            ValueOrigin.FETCHED_HISTORY,
            history_freshness,
        )
        self._set_field_text(
            self.week_52_low,
            self._format_decimal(metrics.lowest_low, places=4),
            ValueOrigin.FETCHED_HISTORY,
            history_freshness,
        )
        self._set_field_text(
            self.week_52_high,
            self._format_decimal(metrics.highest_high, places=4),
            ValueOrigin.FETCHED_HISTORY,
            history_freshness,
        )
        if metrics.average_volume is not None:
            self._set_field_text(
                self.average_volume,
                f"{metrics.average_volume:,.0f}",
                ValueOrigin.FETCHED_HISTORY,
                history_freshness,
            )
        if self.last_quote is not None:
            self._set_field_text(
                self.current_price,
                self._format_decimal(self.last_quote.last_price, places=4),
                ValueOrigin.FETCHED_QUOTE,
                self.last_quote.freshness_label,
            )
        else:
            self._set_field_text(
                self.current_price,
                self._format_decimal(metrics.last_close, places=4),
                ValueOrigin.FETCHED_HISTORY,
                history_freshness,
            )
        self.status_label.setText("Fetched values applied")
        self._update_quote_comparison()

    def use_average_high_low(self) -> None:
        """Compatibility alias for applying all fetched market values."""
        self.apply_fetched_range()

    def clear_fetched_values(self) -> None:
        """Clear previews and values that still derive from a market fetch."""
        for field_key in self._PROVENANCE_FIELDS:
            origin = self._field_origins[field_key]
            if origin in {
                ValueOrigin.FETCHED_HISTORY,
                ValueOrigin.FETCHED_QUOTE,
                ValueOrigin.USER_ADJUSTED,
            }:
                edit = getattr(self, field_key)
                reset_text = "" if field_key == "average_volume" else "0"
                self._set_field_text(edit, reset_text, ValueOrigin.MANUAL)

        self.last_metrics = None
        self.last_quote = None
        self._last_metrics_from_cache = False
        self._last_quote_from_cache = False
        self.apply_range_button.setEnabled(False)
        self._update_market_cards(None, False, None, False)
        self.status_label.setText("Fetched data cleared. Manual entry remains available.")
        self._update_quote_comparison()

    def copy_result_summary(self) -> None:
        """Copy the current calculation with provenance and freshness context."""
        if self.last_result is None:
            return
        QApplication.clipboard().setText(self._summary_text(self.last_result))
        self.status_label.setText("Range summary copied.")

    def _execute_fetch(self, request: _FetchRequest) -> _FetchOutcome:
        started = time.perf_counter()
        outcome = _FetchOutcome(
            symbol=request.symbol,
            lookback_days=request.lookback_days,
            provider_name=request.provider.provider_name,
        )
        try:
            if not request.online_enabled:
                raise MarketDataDisabledError()
            if not request.symbol:
                outcome.error_message = "Enter a ticker or symbol before fetching market numbers."
                return outcome

            provider = request.provider
            self.market_data_cache.historical_ttl = timedelta(hours=24)
            self.market_data_cache.quote_ttl = timedelta(minutes=request.quote_cache_minutes)
            logger.info(
                "market_data_fetch_start provider=%s symbol=%s lookback=%s",
                provider.provider_name,
                request.symbol,
                request.lookback_days,
            )
            quote, quote_from_cache = self._fetch_quote(provider, request.symbol)
            metrics, metrics_from_cache = self._fetch_historical_metrics(
                provider, request.symbol, request.lookback_days
            )
            outcome.metrics = metrics
            outcome.metrics_from_cache = metrics_from_cache
            outcome.quote = quote
            outcome.quote_from_cache = quote_from_cache
        except MarketDataError as exc:
            outcome.error_message = str(exc)
            logger.info(
                "market_data_fetch_failed provider=%s symbol=%s error_category=%s",
                outcome.provider_name,
                request.symbol,
                exc.__class__.__name__,
            )
        except Exception:
            outcome.error_message = "Market data provider is unavailable."
            logger.exception(
                "market_data_fetch_unexpected provider=%s symbol=%s",
                outcome.provider_name,
                request.symbol,
            )
        finally:
            outcome.elapsed_seconds = time.perf_counter() - started
        return outcome

    def _apply_fetch_outcome(self, outcome: _FetchOutcome) -> HistoricalRangeMetrics | None:
        if outcome.error_message:
            retained = self.last_metrics is not None or self.last_quote is not None
            if retained:
                self.status_label.setText(
                    f"{outcome.error_message} Previous market-data values were kept."
                )
            else:
                self.status_label.setText(outcome.error_message)
            self.fetch_failed.emit()
            return None
        if outcome.metrics is None:
            retained = self.last_metrics is not None or self.last_quote is not None
            message = "Market data provider is unavailable."
            if retained:
                message = f"{message} Previous market-data values were kept."
            self.status_label.setText(message)
            self.fetch_failed.emit()
            return None

        had_prior = self.last_metrics is not None
        self._apply_market_data(
            outcome.metrics,
            outcome.metrics_from_cache,
            outcome.quote,
            outcome.quote_from_cache,
        )
        if had_prior and not outcome.metrics_from_cache:
            self.status_label.setText("Historical data refreshed successfully.")
        logger.info(
            "market_data_fetch_ok provider=%s symbol=%s lookback=%s "
            "result_count=%s elapsed_seconds=%.3f cached=%s",
            outcome.provider_name,
            outcome.symbol,
            outcome.lookback_days,
            outcome.metrics.bar_count,
            outcome.elapsed_seconds,
            outcome.metrics_from_cache,
        )
        self.fetch_succeeded.emit()
        return outcome.metrics

    def _on_fetch_worker_finished(self, outcome: object) -> None:
        if not isinstance(outcome, _FetchOutcome):
            self.status_label.setText("Market data provider is unavailable.")
            self.fetch_failed.emit()
        else:
            self._apply_fetch_outcome(outcome)
        self._set_fetch_buttons_enabled(True)
        self._fetch_in_progress = False

    def _on_fetch_thread_finished(self) -> None:
        self._fetch_thread = None
        self._fetch_worker = None
        self._fetch_in_progress = False
        self._set_fetch_buttons_enabled(True)

    def _set_fetch_buttons_enabled(self, enabled: bool) -> None:
        self.fetch_button.setEnabled(enabled)
        self.refresh_button.setEnabled(enabled)

    def _detach_fetch_worker(self) -> None:
        thread = self._fetch_thread
        if thread is None:
            return
        try:
            if self._fetch_worker is not None:
                self._fetch_worker.finished.disconnect(self._on_fetch_worker_finished)
        except (RuntimeError, TypeError):
            pass
        if thread.isRunning():
            thread.quit()
            thread.wait(1000)

    def _fetch_quote(
        self, provider: MarketDataProvider, symbol: str
    ) -> tuple[MarketDataQuote | None, bool]:
        if not provider.supports_quotes:
            return None, False
        cached = self.market_data_cache.get_quote(provider.provider_name, symbol)
        if cached is not None:
            return cached.quote, True
        try:
            quote = provider.fetch_quote(symbol)
        except MarketDataError:
            return None, False
        cached_quote = self.market_data_cache.set_quote(provider.provider_name, symbol, quote)
        return cached_quote.quote, False

    def _fetch_historical_metrics(
        self,
        provider: MarketDataProvider,
        symbol: str,
        lookback_days: int,
    ) -> tuple[HistoricalRangeMetrics, bool]:
        cached = self.market_data_cache.get_historical_bars(
            provider.provider_name, symbol, lookback_days
        )
        freshness = self._historical_freshness(provider)
        if cached is not None:
            metrics = calculate_historical_range_metrics(
                cached.bars,
                lookback_days,
                source=cached.provider,
                fetched_at=cached.fetched_at,
                freshness_label=freshness,
            )
            return metrics, True

        try:
            bars = provider.fetch_daily_bars(symbol, lookback_days)
        except MarketDataError:
            stale = self.market_data_cache.get_historical_bars(
                provider.provider_name,
                symbol,
                lookback_days,
                allow_stale=True,
            )
            if stale is None:
                raise
            metrics = calculate_historical_range_metrics(
                stale.bars,
                lookback_days,
                source=stale.provider,
                fetched_at=stale.fetched_at,
                freshness_label="cached",
            )
            return metrics, True

        cached = self.market_data_cache.set_historical_bars(
            provider.provider_name,
            symbol,
            lookback_days,
            bars,
        )
        metrics = calculate_historical_range_metrics(
            cached.bars,
            lookback_days,
            source=cached.provider,
            fetched_at=cached.fetched_at,
            freshness_label=freshness,
        )
        return metrics, False

    @staticmethod
    def _historical_freshness(provider: MarketDataProvider) -> str:
        return str(getattr(provider, "historical_freshness_label", provider.freshness_label))

    def _current_provider(self) -> MarketDataProvider:
        if self.injected_provider is not None:
            return self.injected_provider
        provider_name = self._active_provider_name()
        provider_class = self.PROVIDER_CLASSES.get(provider_name, AlphaVantageProvider)
        api_key = self.secret_store.get_secret(provider_name) or ""
        if provider_class.requires_api_key and not api_key:
            raise MissingApiKeyError()
        return provider_class(api_key=api_key)

    def _apply_market_data(
        self,
        metrics: HistoricalRangeMetrics,
        metrics_from_cache: bool,
        quote: MarketDataQuote | None,
        quote_from_cache: bool,
    ) -> None:
        """Update previews only; applying values remains an explicit user action."""
        self.last_metrics = metrics
        self.last_quote = quote
        self._last_metrics_from_cache = metrics_from_cache
        self._last_quote_from_cache = quote_from_cache
        self.apply_range_button.setEnabled(True)
        self._update_market_cards(
            metrics,
            metrics_from_cache,
            quote,
            quote_from_cache,
        )
        if metrics.bar_count < metrics.lookback_days:
            self.status_label.setText(
                "The provider returned fewer historical bars than requested. "
                "Review the previews before applying."
            )
        else:
            self.status_label.setText(
                "Market numbers fetched. Review the quote and history cards, "
                "then apply the fetched range if wanted."
            )

    def _update_market_cards(
        self,
        metrics: HistoricalRangeMetrics | None,
        metrics_from_cache: bool,
        quote: MarketDataQuote | None,
        quote_from_cache: bool,
    ) -> None:
        """Refresh separate quote and historical preview cards."""
        if quote is None:
            self.quote_price_value.setText("Unavailable")
            self.quote_day_high_value.setText("Unavailable")
            self.quote_day_low_value.setText("Unavailable")
            self.quote_previous_close_value.setText("Unavailable")
            self.quote_volume_value.setText("Unavailable")
            self.quote_provider_value.setText("Unavailable")
            self.quote_freshness_badge.setText("NOT FETCHED")
            self.quote_fetched_value.setText("Not fetched")
            self.quote_cache_badge.setText("Not fetched")
            quote_status = "NOT FETCHED"
            quote_source = "Unavailable"
            quote_timestamp = "Not fetched"
        else:
            quote_status = status_badge_for_freshness(
                quote.freshness_label, from_cache=quote_from_cache
            )
            quote_source = quote.source or self._active_provider_name()
            quote_timestamp = self._format_optional_timestamp(quote.fetched_at)
            self.quote_price_value.setText(self._metric_text(quote.last_price))
            self.quote_day_high_value.setText(self._metric_text(quote.day_high))
            self.quote_day_low_value.setText(self._metric_text(quote.day_low))
            self.quote_previous_close_value.setText(self._metric_text(quote.previous_close))
            self.quote_volume_value.setText(self._metric_text(quote.volume))
            self.quote_provider_value.setText(quote_source)
            self.quote_freshness_badge.setText(quote_status)
            self.quote_fetched_value.setText(quote_timestamp)
            self.quote_cache_badge.setText("CACHED" if quote_from_cache else "LIVE FETCH")

        if metrics is None:
            self.history_requested_value.setText("Not fetched")
            self.history_bars_value.setText("Unavailable")
            self.history_dates_value.setText("Unavailable")
            self.history_average_low_value.setText("Unavailable")
            self.history_average_high_value.setText("Unavailable")
            self.history_52_low_value.setText("Unavailable")
            self.history_52_high_value.setText("Unavailable")
            self.history_average_volume_value.setText("Unavailable")
            self.history_provider_value.setText("Unavailable")
            self.history_status_badge.setText("NOT FETCHED")
            self.history_fetched_value.setText("Not fetched")
            self.history_cache_badge.setText("Not fetched")
            self.history_cache_notice.clear()
            self.history_cache_notice.hide()
            self.history_fewer_bars_notice.clear()
            self.history_fewer_bars_notice.hide()
            history_status = "NOT FETCHED"
            history_source = "Unavailable"
            history_timestamp = "Not fetched"
            lookback_text = "Not fetched"
        else:
            history_status = status_badge_for_freshness(
                metrics.freshness_label, from_cache=metrics_from_cache
            )
            history_source = metrics.source or self._active_provider_name()
            history_timestamp = self._format_timestamp(metrics.fetched_at)
            lookback_text = (
                f"{metrics.lookback_days} trading days requested · {metrics.bar_count} bars used"
            )
            self.history_requested_value.setText(f"{metrics.lookback_days} trading days")
            self.history_bars_value.setText(str(metrics.bar_count))
            self.history_dates_value.setText(
                f"{metrics.start_date.isoformat()} through {metrics.end_date.isoformat()}"
            )
            self.history_average_low_value.setText(self._metric_text(metrics.average_low))
            self.history_average_high_value.setText(self._metric_text(metrics.average_high))
            self.history_52_low_value.setText(self._metric_text(metrics.lowest_low))
            self.history_52_high_value.setText(self._metric_text(metrics.highest_high))
            self.history_average_volume_value.setText(self._metric_text(metrics.average_volume))
            self.history_provider_value.setText(history_source)
            self.history_status_badge.setText(history_status)
            self.history_fetched_value.setText(history_timestamp)
            self.history_cache_badge.setText("CACHED" if metrics_from_cache else "LIVE FETCH")
            if metrics_from_cache:
                friendly = metrics.fetched_at.astimezone().strftime("%B %d, %Y at %I:%M %p")
                self.history_cache_notice.setText(
                    f"Using cached historical data from {friendly}."
                )
                self.history_cache_notice.show()
            else:
                self.history_cache_notice.clear()
                self.history_cache_notice.hide()
            if metrics.bar_count < metrics.lookback_days:
                self.history_fewer_bars_notice.setText(
                    "The provider returned fewer historical bars than requested."
                )
                self.history_fewer_bars_notice.show()
            else:
                self.history_fewer_bars_notice.clear()
                self.history_fewer_bars_notice.hide()

        self.source_value.setText(f"Quote: {quote_source} · History: {history_source}")
        if metrics_from_cache or quote_from_cache:
            self.fetched_value.setText(
                f"Quote: {quote_timestamp} · History: {history_timestamp} (cached)"
            )
        else:
            self.fetched_value.setText(f"Quote: {quote_timestamp} · History: {history_timestamp}")
        self.freshness_value.setText(f"Quote: {quote_status} · History: {history_status}")
        self.lookback_value.setText(lookback_text)
        if metrics is None and quote is None:
            self.cache_status_value.setText("Not fetched")
        elif metrics_from_cache or quote_from_cache:
            self.cache_status_value.setText("Cached")
        else:
            self.cache_status_value.setText("Live fetch")

    def _set_field_text(
        self,
        edit: QLineEdit,
        text: str,
        origin: ValueOrigin,
        freshness: str = "",
    ) -> None:
        """Set an editable value without treating it as a user adjustment."""
        field_key = self._field_key_for_edit(edit)
        if field_key is None:
            edit.setText(text)
            return
        self._programmatic_field_update = True
        try:
            self._field_origins[field_key] = origin
            self._field_freshness[field_key] = freshness
            edit.setText(text)
        finally:
            self._programmatic_field_update = False
        self._refresh_badges()

    def _field_key_for_edit(self, edit: QLineEdit) -> str | None:
        for field_key in self._PROVENANCE_FIELDS:
            if getattr(self, field_key) is edit:
                return field_key
        return None

    def _on_field_edited(self, field_key: str) -> None:
        """Mark fetched values as adjusted when the user edits them."""
        if not self._programmatic_field_update:
            if field_key == "planned_buy_price":
                self._planned_buy_from_holding = False
            origin = self._field_origins[field_key]
            if origin in {
                ValueOrigin.FETCHED_HISTORY,
                ValueOrigin.FETCHED_QUOTE,
            }:
                self._field_origins[field_key] = ValueOrigin.USER_ADJUSTED
                self._field_freshness[field_key] = ""
                self._refresh_badges()
        if field_key in {"planned_buy_price", "current_price"}:
            self._update_quote_comparison()

    def _refresh_badges(self) -> None:
        """Refresh all field provenance badges and tooltips."""
        for field_key, badge in self._field_badges.items():
            label = badge_label_for_origin(
                self._field_origins[field_key],
                self._field_freshness[field_key],
            )
            badge.setText(label)
            badge.setToolTip(BADGE_TOOLTIPS.get(label, "Value provenance"))

    def _update_quote_comparison(self, _text: str = "") -> None:
        """Update the neutral quote comparison from current editable values."""
        required = (
            self.shares.text().strip(),
            self.planned_buy_price.text().strip(),
            self.current_price.text().strip(),
        )
        if not all(required):
            self._clear_quote_comparison()
            return
        try:
            if any(to_decimal(value) <= 0 for value in required):
                self._clear_quote_comparison()
                return
            comparison = calculate_quote_comparison(
                self.shares.text(),
                self.planned_buy_price.text(),
                self.buy_fees.text(),
                self.sell_fees.text(),
                self.current_price.text(),
            )
        except (ArithmeticError, ValueError):
            self._clear_quote_comparison()
            return
        self.comparison_quote_value.setText(self._format_money(comparison.current_quote))
        self.comparison_per_share_value.setText(
            self._format_signed_money(comparison.per_share_difference)
        )
        self.comparison_position_value.setText(
            self._format_signed_money(comparison.position_difference)
        )
        self.comparison_roi_value.setText(self._format_signed_percent(comparison.roi_percent))

    def _clear_quote_comparison(self) -> None:
        for label in (
            self.comparison_quote_value,
            self.comparison_per_share_value,
            self.comparison_position_value,
            self.comparison_roi_value,
        ):
            label.setText("Unavailable")

    @staticmethod
    def _metric_text(value: Decimal | int | None) -> str:
        """Format preview metrics without substituting fake zero values."""
        if value is None:
            return "Unavailable"
        if isinstance(value, int):
            return f"{value:,}"
        return f"{value:,.4f}"

    def _clear_results(self) -> None:
        for label in self.result_labels.values():
            label.setText("--")

    def _populate_results(self, result: RangeScenarioResult) -> None:
        money_fields = {
            "entry_cost",
            "low_value",
            "high_value",
            "low_profit",
            "high_profit",
            "break_even_price",
            "price_spread",
            "gain_per_share_at_high",
            "loss_per_share_at_low",
        }
        percent_fields = {"low_roi_percent", "high_roi_percent", "spread_percent"}
        for key, label in self.result_labels.items():
            value = getattr(result, key)
            if key in money_fields:
                label.setText(self._format_money(value))
            elif key in percent_fields:
                label.setText(self._format_percent(value))
            else:
                label.setText(str(value))

    def _summary_text(self, result: RangeScenarioResult) -> str:
        provider = self.last_metrics.source if self.last_metrics is not None else ""
        low_phrase, _ = summary_low_high_phrase(self._field_origins["average_low_price"])
        _, high_phrase = summary_low_high_phrase(self._field_origins["average_high_price"])
        if self._planned_buy_from_holding:
            buy_line = "Buy price: Loaded from selected holding"
        else:
            buy_line = provenance_line(
                "Buy price",
                self._field_origins["planned_buy_price"],
                provider,
            )
        current_origin = self._field_origins["current_price"]
        quote_provider = self.last_quote.source if self.last_quote is not None else provider
        if current_origin is ValueOrigin.FETCHED_QUOTE and self.last_quote is not None:
            current_line = (
                f"Current quote: {quote_provider}, {self.last_quote.freshness_label}"
            )
        else:
            current_line = provenance_line("Current quote", current_origin, quote_provider)
        provenance_lines = [
            "Range inputs:",
            provenance_line(
                "Low",
                self._field_origins["average_low_price"],
                provider,
            ),
            provenance_line(
                "High",
                self._field_origins["average_high_price"],
                provider,
            ),
            buy_line,
            current_line,
        ]
        market_lines: list[str] = []
        if self.last_metrics is not None:
            market_lines = [
                f"Market sources: {self.source_value.text()}",
                f"Requested lookback: {self.last_metrics.lookback_days} trading days",
                f"Bars used: {self.last_metrics.bar_count}",
                (
                    "Period: "
                    f"{self.last_metrics.start_date.isoformat()} through "
                    f"{self.last_metrics.end_date.isoformat()}"
                ),
                f"Quote freshness: {self.quote_freshness_badge.text()}",
                f"History freshness: {self.history_status_badge.text()}",
                f"Quote fetched: {self.quote_fetched_value.text()}",
                f"History fetched: {self.history_fetched_value.text()}",
            ]
        return "\n".join(
            [
                f"Range scenario for {result.symbol_name}",
                *market_lines,
                *provenance_lines,
                f"Shares: {result.shares}",
                f"Entry cost: {self._format_money(result.entry_cost)}",
                f"{low_phrase}: {self._format_money(result.low_value)}",
                f"{high_phrase}: {self._format_money(result.high_value)}",
                f"Possible gain/loss at low: {self._format_money(result.low_profit)}",
                f"Possible gain/loss at high: {self._format_money(result.high_profit)}",
                f"ROI at low: {self._format_percent(result.low_roi_percent)}",
                f"ROI at high: {self._format_percent(result.high_roi_percent)}",
                f"Break-even price: {self._format_money(result.break_even_price)}",
                f"Price spread: {self._format_money(result.price_spread)}",
                f"Spread percent: {self._format_percent(result.spread_percent)}",
                f"Goblin note: {result.goblin_note}",
                (
                    "No brokerage sync, trade execution, prediction, recommendation, "
                    "or investment advice."
                ),
            ]
        )

    @staticmethod
    def _format_money(value: Decimal) -> str:
        return f"${value:,.2f}"

    @staticmethod
    def _format_signed_money(value: Decimal) -> str:
        prefix = "+" if value > 0 else ""
        return f"{prefix}${value:,.2f}"

    @staticmethod
    def _format_percent(value: Decimal) -> str:
        return f"{value:,.2f}%"

    @staticmethod
    def _format_signed_percent(value: Decimal) -> str:
        prefix = "+" if value > 0 else ""
        return f"{prefix}{value:,.2f}%"

    @staticmethod
    def _format_decimal(value: Decimal, places: int) -> str:
        quant = Decimal("1").scaleb(-places)
        return str(value.quantize(quant))

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone().strftime("%Y-%m-%d %H:%M")

    @classmethod
    def _format_optional_timestamp(cls, value: datetime | None) -> str:
        return cls._format_timestamp(value) if value is not None else "Unavailable"
