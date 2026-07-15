from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gaingoblin.calculations import to_decimal
from gaingoblin.market_data.cache import MarketDataCache
from gaingoblin.market_data.errors import MarketDataDisabledError, MarketDataError
from gaingoblin.market_data.historical_range import calculate_historical_range_metrics
from gaingoblin.market_data.models import HistoricalRangeMetrics, MarketDataQuote
from gaingoblin.market_data.provider_base import MarketDataProvider
from gaingoblin.market_data.providers.alpha_vantage_provider import AlphaVantageProvider
from gaingoblin.market_data.providers.mock_provider import MockProvider
from gaingoblin.market_data.providers.nasdaq_data_link_provider import NasdaqDataLinkProvider
from gaingoblin.market_data.providers.polygon_provider import PolygonProvider
from gaingoblin.market_data.secret_store import MemorySecretStore, SecretStore
from gaingoblin.market_data.settings import (
    MASKED_API_KEY_PLACEHOLDER,
    MarketDataSettings,
    MarketDataSettingsStore,
)
from gaingoblin.models import Holding
from gaingoblin.range_calculator import (
    RangeScenarioInput,
    RangeScenarioResult,
    calculate_range_scenario,
)
from gaingoblin.widgets.dialog_utils import center_and_clamp_dialog
from gaingoblin.widgets.holding_dialog import MoneyEdit

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
        outcome = self._dialog._execute_fetch(self._request)
        self.finished.emit(outcome)


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
        "Alpha Vantage": AlphaVantageProvider,
        "Polygon": PolygonProvider,
        "Nasdaq Data Link": NasdaqDataLinkProvider,
    }

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
            self.secret_store = getattr(self.settings_store, "secret_store", None) or MemorySecretStore()
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
        self._has_stored_api_key = False
        self._fetch_thread: QThread | None = None
        self._fetch_worker: _FetchWorker | None = None
        self._fetch_in_progress = False

        self.setWindowTitle("Range Profit Calculator")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.resize(900, 780)
        self.setMinimumSize(600, 500)

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
        self.load_selected_button.setEnabled(selected_holding is not None)
        self.load_selected_button.clicked.connect(self.load_selected_holding)

        input_host = QWidget()
        input_host.setMaximumWidth(720)
        input_form = QFormLayout(input_host)
        input_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        input_form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
        input_form.addRow("Ticker / Symbol", self.symbol_name)
        input_form.addRow("Shares", self.shares)
        input_form.addRow("Planned Buy Price", self.planned_buy_price)
        input_form.addRow("Average Low Price", self.average_low_price)
        input_form.addRow("Average High Price", self.average_high_price)
        input_form.addRow("Buy Fees", self.buy_fees)
        input_form.addRow("Sell Fees", self.sell_fees)
        input_form.addRow("Optional 52-Week Low", self.week_52_low)
        input_form.addRow("Optional 52-Week High", self.week_52_high)
        input_form.addRow("Optional Current Price", self.current_price)
        input_form.addRow("Optional Average Volume", self.average_volume)
        input_form.addRow("Notes", self.notes)

        self.scout_panel = QFrame()
        self.scout_panel.setObjectName("RangeResultsPanel")
        scout_layout = QFormLayout(self.scout_panel)
        scout_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        self.online_enabled = QCheckBox("Enable Market Data Scout")
        self.online_enabled.setChecked(self.settings.market_data_enabled)
        self.provider_combo = QComboBox()
        provider_names = (
            [self.injected_provider.provider_name]
            if self.injected_provider
            else list(self.PROVIDER_CLASSES)
        )
        self.provider_combo.addItems(provider_names)
        if self.settings.selected_provider in provider_names:
            self.provider_combo.setCurrentText(self.settings.selected_provider)
        self.provider_combo.currentTextChanged.connect(self._refresh_api_key_field)
        self.lookback_combo = QComboBox()
        for label, value in self.LOOKBACK_WINDOWS:
            self.lookback_combo.addItem(label, value)
        self.lookback_combo.setCurrentIndex(2)
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("API key, if provider requires one")
        self.cache_minutes = QSpinBox()
        self.cache_minutes.setRange(1, 10080)
        self.cache_minutes.setValue(self.settings.cache_duration_minutes)
        self.fetch_button = QPushButton("Fetch Market Numbers")
        self.fetch_button.clicked.connect(self.start_market_data_fetch)
        self.use_average_button = QPushButton("Use Average High/Low")
        self.use_average_button.setEnabled(False)
        self.use_average_button.clicked.connect(self.use_average_high_low)
        self.clear_fetch_button = QPushButton("Clear Fetched Data")
        self.clear_fetch_button.clicked.connect(self.clear_fetched_values)
        self.clear_api_key_button = QPushButton("Clear Saved API Key")
        self.clear_api_key_button.clicked.connect(self.clear_saved_api_key)
        self.source_value = QLabel("Not fetched")
        self.fetched_value = QLabel("Not fetched")
        self.freshness_value = QLabel("unknown")
        self.lookback_value = QLabel("Not fetched")
        self.cache_status_value = QLabel("Not fetched")
        self.delay_value = self.freshness_value
        self.market_warning = QLabel(MARKET_DATA_WARNING)
        self.market_warning.setObjectName("HelperText")
        self.market_warning.setWordWrap(True)
        self.historical_warning = self.market_warning
        scout_layout.addRow("", QLabel("Market Data Scout"))
        scout_layout.addRow("Symbol", QLabel("Uses Ticker / Symbol field above"))
        scout_layout.addRow("", self.online_enabled)
        scout_layout.addRow("Provider", self.provider_combo)
        scout_layout.addRow("Lookback Window", self.lookback_combo)
        scout_layout.addRow("API Key", self.api_key_edit)
        scout_layout.addRow("Quote Cache (minutes)", self.cache_minutes)
        scout_layout.addRow("Data Source", self.source_value)
        scout_layout.addRow("Fetched Timestamp", self.fetched_value)
        scout_layout.addRow("Freshness", self.freshness_value)
        scout_layout.addRow("Lookback Period", self.lookback_value)
        scout_layout.addRow("Cached Status", self.cache_status_value)
        scout_layout.addRow("", self.fetch_button)
        scout_layout.addRow("", self.use_average_button)
        scout_layout.addRow("", self.clear_fetch_button)
        scout_layout.addRow("", self.clear_api_key_button)
        scout_layout.addRow("", self.market_warning)

        self.results_panel = QFrame()
        self.results_panel.setObjectName("RangeResultsPanel")
        self.result_labels: dict[str, QLabel] = {}
        results_form = QFormLayout(self.results_panel)
        results_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        for key, label in self.RESULT_FIELDS:
            value = QLabel("--")
            value.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            value.setWordWrap(True)
            self.result_labels[key] = value
            results_form.addRow(label, value)

        form_shell = QWidget()
        form_shell_layout = QVBoxLayout(form_shell)
        form_shell_layout.addWidget(intro)
        form_shell_layout.addWidget(self.status_label)
        form_shell_layout.addWidget(self.load_selected_button, alignment=Qt.AlignmentFlag.AlignLeft)
        form_shell_layout.addWidget(input_host, alignment=Qt.AlignmentFlag.AlignHCenter)
        form_shell_layout.addWidget(self.scout_panel)
        form_shell_layout.addWidget(self.results_panel)

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

        self._refresh_api_key_field()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_and_clamp_dialog(self, self.parentWidget())

    def closeEvent(self, event) -> None:
        self._detach_fetch_worker()
        super().closeEvent(event)

    def load_selected_holding(self) -> None:
        if self.selected_holding is None:
            return
        holding = self.selected_holding
        self.symbol_name.setText(holding.symbol_name)
        self.shares.setText(str(holding.shares))
        self.planned_buy_price.setText(str(holding.buy_price))
        self.buy_fees.setText(str(holding.buy_fees))
        self.sell_fees.setText(str(holding.sell_fees))
        if not self.notes.toPlainText().strip() and holding.notes:
            self.notes.setPlainText(holding.notes)
        self.status_label.setText(
            "Selected holding loaded. Enter average low and high values to calculate the range."
        )

    def scenario_input(self) -> RangeScenarioInput:
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
        try:
            result = calculate_range_scenario(self.scenario_input())
        except ValueError as exc:
            self.last_result = None
            self.copy_button.setEnabled(False)
            self.status_label.setText(str(exc))
            self._clear_results()
            self.validation_failed.emit()
            return None

        self.last_result = result
        self._populate_results(result)
        self.copy_button.setEnabled(True)
        self.status_label.setText("Projected math tallied from your editable range values.")
        self.calculation_succeeded.emit()
        return result

    def fetch_historical_range(self) -> HistoricalRangeMetrics | None:
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

        try:
            self._save_market_data_settings()
            request = self._build_fetch_request()
        except Exception:
            logger.exception("Failed to prepare market-data fetch")
            self.status_label.setText("Market data provider is unavailable.")
            self.fetch_failed.emit()
            return

        self._fetch_in_progress = True
        self.fetch_button.setEnabled(False)
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
        """Synchronous scout used by tests and the background worker."""
        self.fetch_started.emit()
        try:
            self._save_market_data_settings()
            request = self._build_fetch_request()
        except Exception:
            logger.exception("Failed to prepare market-data fetch")
            self.status_label.setText("Market data provider is unavailable.")
            self.fetch_failed.emit()
            return None
        outcome = self._execute_fetch(request)
        return self._apply_fetch_outcome(outcome)

    def _build_fetch_request(self) -> _FetchRequest:
        return _FetchRequest(
            symbol=self.symbol_name.text().strip().upper(),
            lookback_days=int(self.lookback_combo.currentData() or 90),
            online_enabled=self.online_enabled.isChecked(),
            provider=self._current_provider(),
            quote_cache_minutes=self.cache_minutes.value(),
        )

    def use_average_high_low(self) -> None:
        if self.last_metrics is None:
            return
        self.average_low_price.setText(self._format_decimal(self.last_metrics.average_low, places=4))
        self.average_high_price.setText(
            self._format_decimal(self.last_metrics.average_high, places=4)
        )
        self.status_label.setText(
            "Historical average high/low copied into editable scenario fields."
        )

    def clear_fetched_values(self) -> None:
        self.last_metrics = None
        self.last_quote = None
        self.use_average_button.setEnabled(False)
        self.average_low_price.setText("0")
        self.average_high_price.setText("0")
        self.week_52_low.setText("0")
        self.week_52_high.setText("0")
        self.current_price.setText("0")
        self.average_volume.clear()
        self.source_value.setText("Not fetched")
        self.fetched_value.setText("Not fetched")
        self.freshness_value.setText("unknown")
        self.lookback_value.setText("Not fetched")
        self.cache_status_value.setText("Not fetched")
        self.status_label.setText("Fetched data cleared. Manual entry remains available.")

    def clear_saved_api_key(self) -> None:
        provider_name = self.provider_combo.currentText()
        try:
            self.secret_store.delete_secret(provider_name)
        except Exception:
            logger.exception("Failed to clear saved API key provider=%s", provider_name)
            self.status_label.setText("Could not clear the saved API key from the credential store.")
            return
        self._has_stored_api_key = False
        self.api_key_edit.clear()
        self.api_key_edit.setPlaceholderText("API key, if provider requires one")
        self._save_market_data_settings(persist_typed_key=False)
        self.status_label.setText("Saved market data API key cleared from the credential store.")
        logger.info("cleared_saved_api_key provider=%s", provider_name)

    def copy_result_summary(self) -> None:
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
            self.status_label.setText(outcome.error_message)
            self.fetch_failed.emit()
            return None
        if outcome.metrics is None:
            self.status_label.setText("Market data provider is unavailable.")
            self.fetch_failed.emit()
            return None

        self._apply_market_data(
            outcome.metrics,
            outcome.metrics_from_cache,
            outcome.quote,
            outcome.quote_from_cache,
        )
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
        self.fetch_button.setEnabled(True)
        self._fetch_in_progress = False

    def _on_fetch_thread_finished(self) -> None:
        self._fetch_thread = None
        self._fetch_worker = None
        self._fetch_in_progress = False
        self.fetch_button.setEnabled(True)

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

    def _fetch_quote(self, provider: MarketDataProvider, symbol: str) -> tuple[MarketDataQuote | None, bool]:
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
        provider_name = self.provider_combo.currentText()
        provider_class = self.PROVIDER_CLASSES.get(provider_name, MockProvider)
        return provider_class(api_key=self._resolve_api_key(provider_name))

    def _resolve_api_key(self, provider_name: str) -> str:
        typed = self.api_key_edit.text().strip()
        if typed and typed != MASKED_API_KEY_PLACEHOLDER:
            return typed
        stored = self.secret_store.get_secret(provider_name)
        return stored or ""

    def _refresh_api_key_field(self, *_args: object) -> None:
        provider_name = self.provider_combo.currentText()
        stored = self.secret_store.get_secret(provider_name)
        self._has_stored_api_key = bool(stored)
        self.api_key_edit.clear()
        if self._has_stored_api_key:
            self.api_key_edit.setPlaceholderText(MASKED_API_KEY_PLACEHOLDER)
        else:
            self.api_key_edit.setPlaceholderText("API key, if provider requires one")

    def _save_market_data_settings(self, *, persist_typed_key: bool = True) -> None:
        if self.injected_provider is not None:
            return
        provider_name = self.provider_combo.currentText()
        if persist_typed_key:
            typed = self.api_key_edit.text().strip()
            if typed and typed != MASKED_API_KEY_PLACEHOLDER:
                try:
                    self.secret_store.set_secret(provider_name, typed)
                    self._has_stored_api_key = True
                    self.api_key_edit.clear()
                    self.api_key_edit.setPlaceholderText(MASKED_API_KEY_PLACEHOLDER)
                except Exception:
                    logger.exception("Failed to persist API key provider=%s", provider_name)
                    raise
        settings = MarketDataSettings(
            market_data_enabled=self.online_enabled.isChecked(),
            selected_provider=provider_name,
            cache_duration_minutes=self.cache_minutes.value(),
        )
        self.settings_store.save(settings)

    def _apply_market_data(
        self,
        metrics: HistoricalRangeMetrics,
        metrics_from_cache: bool,
        quote: MarketDataQuote | None,
        quote_from_cache: bool,
    ) -> None:
        self.last_metrics = metrics
        self.last_quote = quote
        self.use_average_button.setEnabled(True)
        self.use_average_high_low()
        self.week_52_low.setText(self._format_decimal(metrics.lowest_low, places=4))
        self.week_52_high.setText(self._format_decimal(metrics.highest_high, places=4))
        if quote is not None:
            self.current_price.setText(self._format_decimal(quote.last_price, places=4))
        else:
            self.current_price.setText(self._format_decimal(metrics.last_close, places=4))
        if metrics.average_volume is not None:
            self.average_volume.setText(f"{metrics.average_volume:,.0f}")

        self.source_value.setText(
            self._source_label(metrics, metrics_from_cache, quote, quote_from_cache)
        )
        timestamp = self._format_timestamp(metrics.fetched_at)
        cache_label = "cached" if metrics_from_cache else "fetched"
        self.fetched_value.setText(
            f"{timestamp} ({cache_label}, {metrics.lookback_days} trading days)"
        )
        self.freshness_value.setText(
            quote.freshness_label if quote is not None else metrics.freshness_label
        )
        self.lookback_value.setText(f"{metrics.lookback_days} trading days")
        self.cache_status_value.setText(
            "Cached" if metrics_from_cache or quote_from_cache else "Live fetch"
        )
        self.status_label.setText(
            "Market numbers fetched. Review and edit every value before calculating."
        )

    @staticmethod
    def _source_label(
        metrics: HistoricalRangeMetrics,
        metrics_from_cache: bool,
        quote: MarketDataQuote | None,
        quote_from_cache: bool,
    ) -> str:
        parts = [f"{metrics.source} history{' cache' if metrics_from_cache else ''}"]
        if quote is not None:
            parts.insert(0, f"{quote.source} quote{' cache' if quote_from_cache else ''}")
        return " + ".join(parts)

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
        source_lines: list[str] = []
        if self.last_metrics is not None:
            source_lines = [
                f"Market values source: {self.source_value.text()}",
                f"Lookback: {self.last_metrics.lookback_days} trading days",
                f"Fetched: {self._format_timestamp(self.last_metrics.fetched_at)}",
                f"Freshness: {self.freshness_value.text()}",
                f"Cached status: {self.cache_status_value.text()}",
            ]
        return "\n".join(
            [
                f"Range scenario for {result.symbol_name}",
                *source_lines,
                f"Shares: {result.shares}",
                f"Entry cost: {self._format_money(result.entry_cost)}",
                f"Value at user-entered average low: {self._format_money(result.low_value)}",
                f"Value at user-entered average high: {self._format_money(result.high_value)}",
                f"Possible gain/loss at low: {self._format_money(result.low_profit)}",
                f"Possible gain/loss at high: {self._format_money(result.high_profit)}",
                f"ROI at low: {self._format_percent(result.low_roi_percent)}",
                f"ROI at high: {self._format_percent(result.high_roi_percent)}",
                f"Break-even price: {self._format_money(result.break_even_price)}",
                f"Price spread: {self._format_money(result.price_spread)}",
                f"Spread percent: {self._format_percent(result.spread_percent)}",
                f"Goblin note: {result.goblin_note}",
                "Manual range math only. No brokerage sync, trade execution, or investment advice.",
            ]
        )

    @staticmethod
    def _format_money(value: Decimal) -> str:
        return f"${value:,.2f}"

    @staticmethod
    def _format_percent(value: Decimal) -> str:
        return f"{value:,.2f}%"

    @staticmethod
    def _format_decimal(value: Decimal, places: int) -> str:
        quant = Decimal("1").scaleb(-places)
        return str(value.quantize(quant))

    @staticmethod
    def _format_timestamp(value: datetime) -> str:
        return value.astimezone().strftime("%Y-%m-%d %H:%M")
