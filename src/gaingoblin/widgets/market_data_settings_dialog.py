"""Dedicated Market Data Settings dialog for Gain Goblin."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
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
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from gaingoblin.market_data.cache import MarketDataCache
from gaingoblin.market_data.errors import (
    AuthenticationError,
    MalformedMarketDataError,
    MarketDataError,
    MissingApiKeyError,
    NetworkUnavailableError,
    ProviderTimeoutError,
    RateLimitError,
)
from gaingoblin.market_data.providers.alpha_vantage_provider import AlphaVantageProvider
from gaingoblin.market_data.secret_store import MemorySecretStore, SecretStore
from gaingoblin.market_data.settings import (
    MASKED_API_KEY_PLACEHOLDER,
    MarketDataSettings,
    MarketDataSettingsStore,
)
from gaingoblin.widgets.dialog_utils import center_and_clamp_dialog

logger = logging.getLogger(__name__)

ALPHA_VANTAGE = "Alpha Vantage"
MOCK_PROVIDER = "Mock"
DEFAULT_TEST_SYMBOL = "IBM"

COMING_LATER_PROVIDERS = (
    ("Polygon / Massive", "Coming Later"),
    ("Nasdaq Data Link", "Coming Later"),
)

CAPABILITY_LINES = (
    "Historical daily bars",
    "Quote support",
    "Data freshness depends on provider plan",
    "Real-time access is not guaranteed",
)


@dataclass(slots=True)
class ConnectionTestResult:
    ok: bool
    message: str
    category: str = ""


class _ConnectionTestWorker(QObject):
    finished = Signal(object)

    def __init__(self, api_key: str, symbol: str) -> None:
        super().__init__()
        self._api_key = api_key
        self._symbol = symbol

    def run(self) -> None:
        result = run_alpha_vantage_connection_test(self._api_key, self._symbol)
        self.finished.emit(result)


def run_alpha_vantage_connection_test(
    api_key: str,
    symbol: str = DEFAULT_TEST_SYMBOL,
    *,
    provider: AlphaVantageProvider | None = None,
) -> ConnectionTestResult:
    """Exercise a quote fetch and map failures to friendly categories."""
    cleaned_key = str(api_key or "").strip()
    if not cleaned_key:
        return ConnectionTestResult(False, "API key is missing.", "missing_key")
    probe = provider or AlphaVantageProvider(api_key=cleaned_key)
    try:
        quote = probe.fetch_quote(symbol)
    except MissingApiKeyError:
        return ConnectionTestResult(False, "API key is missing.", "missing_key")
    except AuthenticationError:
        return ConnectionTestResult(False, "Invalid API key.", "invalid_key")
    except RateLimitError:
        return ConnectionTestResult(False, "Provider rate limit was reached.", "rate_limit")
    except ProviderTimeoutError:
        return ConnectionTestResult(False, "Provider request timed out.", "timeout")
    except NetworkUnavailableError:
        return ConnectionTestResult(False, "Internet connection failed.", "network")
    except MalformedMarketDataError:
        return ConnectionTestResult(
            False,
            "Market data provider returned data Gain Goblin could not read.",
            "malformed",
        )
    except MarketDataError as exc:
        return ConnectionTestResult(False, str(exc), exc.__class__.__name__)
    except Exception:
        logger.exception("connection_test_unexpected provider=%s symbol=%s", ALPHA_VANTAGE, symbol)
        return ConnectionTestResult(False, "Market data provider is unavailable.", "unexpected")

    logger.info(
        "connection_test_ok provider=%s symbol=%s freshness=%s",
        ALPHA_VANTAGE,
        quote.symbol,
        quote.freshness_label,
    )
    return ConnectionTestResult(
        True,
        f"Connection succeeded for {quote.symbol}. Review settings and save to enable Online Market Data.",
        "success",
    )


class MarketDataSettingsDialog(QDialog):
    """Guided Alpha Vantage setup with secure credential handling."""

    settings_saved = Signal()
    connection_test_finished = Signal(object)

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        settings_store: MarketDataSettingsStore | None = None,
        secret_store: SecretStore | None = None,
        market_data_cache: MarketDataCache | None = None,
        test_symbol: str = DEFAULT_TEST_SYMBOL,
        connection_tester: Callable[..., ConnectionTestResult] | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings_store = settings_store or MarketDataSettingsStore.default()
        if secret_store is not None:
            self.secret_store = secret_store
        else:
            self.secret_store = getattr(self.settings_store, "secret_store", None) or MemorySecretStore()
            self.settings_store.secret_store = self.secret_store
        self.market_data_cache = market_data_cache or MarketDataCache.default()
        self.test_symbol = (test_symbol or DEFAULT_TEST_SYMBOL).strip().upper() or DEFAULT_TEST_SYMBOL
        self._connection_tester = connection_tester or run_alpha_vantage_connection_test
        self.settings = self._normalized_settings(self.settings_store.load())
        self._has_stored_key = bool(self.secret_store.get_secret(ALPHA_VANTAGE))
        self._connection_failed = False
        self._test_thread: QThread | None = None
        self._test_worker: _ConnectionTestWorker | None = None
        self._test_in_progress = False

        self.setWindowTitle("Market Data Settings")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.resize(640, 700)
        self.setMinimumSize(520, 480)

        intro = QLabel(
            "Configure optional online market data for the Range Calculator. "
            "Alpha Vantage is the supported provider in this release. "
            "Keys are stored in the operating-system credential store, not in JSON files."
        )
        intro.setObjectName("HelperText")
        intro.setWordWrap(True)

        self.status_label = QLabel("")
        self.status_label.setObjectName("HelperText")
        self.status_label.setWordWrap(True)

        provider_frame = QFrame()
        provider_frame.setObjectName("RangeResultsPanel")
        provider_form = QFormLayout(provider_frame)
        provider_form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.provider_name_label = QLabel(ALPHA_VANTAGE)
        self.provider_status_label = QLabel("Not configured")
        self.api_key_edit = QLineEdit()
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.api_key_edit.setPlaceholderText("Paste a new Alpha Vantage API key")
        self.save_key_button = QPushButton("Save Key")
        self.save_key_button.clicked.connect(self.save_api_key)
        self.test_connection_button = QPushButton("Test Connection")
        self.test_connection_button.clicked.connect(self.start_connection_test)
        self.clear_key_button = QPushButton("Clear Key")
        self.clear_key_button.clicked.connect(self.clear_api_key)
        self.online_enabled = QCheckBox("Enable Online Market Data")
        self.online_enabled.setChecked(self.settings.market_data_enabled)
        self.online_enabled.stateChanged.connect(lambda _state: self._refresh_status_label())
        self.cache_minutes = QSpinBox()
        self.cache_minutes.setRange(1, 10080)
        self.cache_minutes.setValue(self.settings.cache_duration_minutes)

        key_row = QWidget()
        key_layout = QHBoxLayout(key_row)
        key_layout.setContentsMargins(0, 0, 0, 0)
        key_layout.addWidget(self.api_key_edit, stretch=1)
        key_layout.addWidget(self.save_key_button)

        action_row = QWidget()
        action_layout = QHBoxLayout(action_row)
        action_layout.setContentsMargins(0, 0, 0, 0)
        action_layout.addWidget(self.test_connection_button)
        action_layout.addWidget(self.clear_key_button)
        action_layout.addStretch(1)

        capability_host = QWidget()
        capability_layout = QVBoxLayout(capability_host)
        capability_layout.setContentsMargins(0, 0, 0, 0)
        for line in CAPABILITY_LINES:
            label = QLabel(f"• {line}")
            label.setObjectName("HelperText")
            label.setWordWrap(True)
            capability_layout.addWidget(label)

        provider_form.addRow("Provider", self.provider_name_label)
        provider_form.addRow("Status", self.provider_status_label)
        provider_form.addRow("API Key", key_row)
        provider_form.addRow("", action_row)
        provider_form.addRow("", self.online_enabled)
        provider_form.addRow("Quote Cache (minutes)", self.cache_minutes)
        provider_form.addRow("Capabilities", capability_host)

        later_frame = QFrame()
        later_frame.setObjectName("RangeResultsPanel")
        later_form = QFormLayout(later_frame)
        later_title = QLabel("Coming Later")
        later_title.setObjectName("HelperText")
        later_form.addRow(later_title)
        self.coming_later_labels: list[QLabel] = []
        for name, badge in COMING_LATER_PROVIDERS:
            label = QLabel(f"{name} — {badge}")
            label.setEnabled(False)
            label.setObjectName("HelperText")
            self.coming_later_labels.append(label)
            later_form.addRow("", label)
        later_note = QLabel(
            "These providers are not selectable yet. Gain Goblin focuses on one polished "
            "Alpha Vantage path before adding more."
        )
        later_note.setObjectName("HelperText")
        later_note.setWordWrap(True)
        later_form.addRow("", later_note)

        cache_frame = QFrame()
        cache_frame.setObjectName("RangeResultsPanel")
        cache_form = QFormLayout(cache_frame)
        self.cache_summary_label = QLabel(self.market_data_cache.summary_text())
        self.cache_summary_label.setObjectName("HelperText")
        self.cache_summary_label.setWordWrap(True)
        self.clear_cache_button = QPushButton("Clear Cache")
        self.clear_cache_button.clicked.connect(self.clear_cache)
        cache_form.addRow("Local Cache", self.cache_summary_label)
        cache_form.addRow("", self.clear_cache_button)

        form_shell = QWidget()
        shell_layout = QVBoxLayout(form_shell)
        shell_layout.addWidget(intro)
        shell_layout.addWidget(self.status_label)
        shell_layout.addWidget(provider_frame)
        shell_layout.addWidget(later_frame)
        shell_layout.addWidget(cache_frame)
        shell_layout.addStretch(1)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setWidget(form_shell)
        self.scroll_area.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.save_and_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.scroll_area)
        layout.addWidget(self.buttons)

        self._refresh_key_field()
        self._refresh_status_label()

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        center_and_clamp_dialog(self, self.parentWidget())

    def closeEvent(self, event) -> None:  # noqa: N802
        self._detach_test_worker()
        super().closeEvent(event)

    def current_settings(self) -> MarketDataSettings:
        return MarketDataSettings(
            market_data_enabled=self.online_enabled.isChecked(),
            selected_provider=ALPHA_VANTAGE,
            cache_duration_minutes=self.cache_minutes.value(),
        )

    def save_api_key(self) -> bool:
        typed = self.api_key_edit.text().strip()
        if not typed or typed == MASKED_API_KEY_PLACEHOLDER:
            self.status_label.setText("Enter a new API key to save, or leave blank to keep the saved key.")
            return False
        try:
            self.secret_store.set_secret(ALPHA_VANTAGE, typed)
        except Exception:
            logger.exception("Failed to save Alpha Vantage API key")
            self.status_label.setText("Could not save the API key to the credential store.")
            return False
        self._has_stored_key = True
        self._connection_failed = False
        self.api_key_edit.clear()
        self._refresh_key_field()
        self._refresh_status_label()
        self.status_label.setText("API key saved to the operating-system credential store.")
        logger.info("api_key_saved provider=%s", ALPHA_VANTAGE)
        return True

    def clear_api_key(self) -> bool:
        answer = QMessageBox.question(
            self,
            "Clear Saved API Key",
            "Remove the saved Alpha Vantage API key from the credential store?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        try:
            self.secret_store.delete_secret(ALPHA_VANTAGE)
        except Exception:
            logger.exception("Failed to clear Alpha Vantage API key")
            self.status_label.setText("Could not clear the saved API key.")
            return False
        self._has_stored_key = False
        self._connection_failed = False
        self.api_key_edit.clear()
        self._refresh_key_field()
        self._refresh_status_label()
        self.status_label.setText("Saved API key cleared from the credential store.")
        logger.info("api_key_cleared provider=%s", ALPHA_VANTAGE)
        return True

    def clear_cache(self) -> bool:
        answer = QMessageBox.question(
            self,
            "Clear Market Data Cache",
            "Clear locally cached market quotes and historical bars?\n"
            "This does not remove your saved API key.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return False
        had_key = bool(self.secret_store.get_secret(ALPHA_VANTAGE))
        self.market_data_cache.clear()
        self.cache_summary_label.setText(self.market_data_cache.summary_text())
        still_has_key = bool(self.secret_store.get_secret(ALPHA_VANTAGE))
        if had_key and not still_has_key:
            logger.error("clear_cache unexpectedly affected API key storage")
        self.status_label.setText("Market data cache cleared. Saved API key was left unchanged.")
        logger.info("market_data_cache_cleared path=%s", self.market_data_cache.path)
        return True

    def start_connection_test(self) -> None:
        if self._test_in_progress:
            return
        api_key = self._resolve_api_key_for_test()
        if not api_key:
            self.status_label.setText("API key is missing.")
            self._connection_failed = True
            self._refresh_status_label()
            self.connection_test_finished.emit(
                ConnectionTestResult(False, "API key is missing.", "missing_key")
            )
            return

        self._test_in_progress = True
        self.test_connection_button.setEnabled(False)
        self.status_label.setText("Testing connection…")
        self._refresh_status_label()

        # Prefer injectible tester for unit tests (sync path on worker can still call it).
        if self._connection_tester is not run_alpha_vantage_connection_test:
            result = self._connection_tester(api_key, self.test_symbol)
            self._on_connection_test_finished(result)
            return

        thread = QThread(self)
        worker = _ConnectionTestWorker(api_key, self.test_symbol)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.finished.connect(self._on_connection_test_finished)
        worker.finished.connect(thread.quit)
        worker.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.finished.connect(self._on_test_thread_finished)
        self._test_thread = thread
        self._test_worker = worker
        thread.start()

    def save_and_accept(self) -> None:
        typed = self.api_key_edit.text().strip()
        if typed and typed != MASKED_API_KEY_PLACEHOLDER:
            if not self.save_api_key():
                return
        settings = self.current_settings()
        if settings.market_data_enabled and not self._has_stored_key:
            self.status_label.setText(
                "Save an Alpha Vantage API key before enabling online market data."
            )
            self._refresh_status_label()
            return
        self.settings_store.save(settings)
        self.settings = settings
        self.settings_saved.emit()
        self.status_label.setText("Market data settings saved.")
        logger.info(
            "market_data_settings_saved enabled=%s provider=%s cache_minutes=%s",
            settings.market_data_enabled,
            settings.selected_provider,
            settings.cache_duration_minutes,
        )
        self.accept()

    def setup_is_ready(self) -> bool:
        settings = self.settings_store.load()
        has_key = bool(self.secret_store.get_secret(ALPHA_VANTAGE))
        return bool(settings.market_data_enabled and has_key)

    def _resolve_api_key_for_test(self) -> str:
        typed = self.api_key_edit.text().strip()
        if typed and typed != MASKED_API_KEY_PLACEHOLDER:
            return typed
        return self.secret_store.get_secret(ALPHA_VANTAGE) or ""

    def _on_connection_test_finished(self, result: object) -> None:
        self._test_in_progress = False
        self.test_connection_button.setEnabled(True)
        if not isinstance(result, ConnectionTestResult):
            self._connection_failed = True
            self.status_label.setText("Market data provider is unavailable.")
            self._refresh_status_label()
            return
        self._connection_failed = not result.ok
        self.status_label.setText(result.message)
        self._refresh_status_label()
        self.connection_test_finished.emit(result)

    def _on_test_thread_finished(self) -> None:
        self._test_thread = None
        self._test_worker = None
        self._test_in_progress = False
        self.test_connection_button.setEnabled(True)

    def _detach_test_worker(self) -> None:
        thread = self._test_thread
        if thread is None:
            return
        try:
            if self._test_worker is not None:
                self._test_worker.finished.disconnect(self._on_connection_test_finished)
        except (RuntimeError, TypeError):
            pass
        if thread.isRunning():
            thread.quit()
            thread.wait(1000)

    def _refresh_key_field(self) -> None:
        self._has_stored_key = bool(self.secret_store.get_secret(ALPHA_VANTAGE))
        if self.api_key_edit.text().strip() and self.api_key_edit.text().strip() != MASKED_API_KEY_PLACEHOLDER:
            return
        self.api_key_edit.clear()
        if self._has_stored_key:
            self.api_key_edit.setPlaceholderText(MASKED_API_KEY_PLACEHOLDER)
        else:
            self.api_key_edit.setPlaceholderText("Paste a new Alpha Vantage API key")

    def _refresh_status_label(self) -> None:
        status = self.compute_provider_status()
        self.provider_status_label.setText(status)

    def compute_provider_status(self) -> str:
        if self._test_in_progress:
            return "Testing connection…"
        if self._connection_failed:
            return "Connection failed"
        if not self.online_enabled.isChecked():
            if self._has_stored_key:
                return "Disabled"
            return "Not configured"
        if not self._has_stored_key:
            return "Not configured"
        return "Ready"

    @staticmethod
    def _normalized_settings(settings: MarketDataSettings) -> MarketDataSettings:
        provider = settings.selected_provider
        if provider not in {ALPHA_VANTAGE, MOCK_PROVIDER}:
            provider = ALPHA_VANTAGE
        return MarketDataSettings(
            market_data_enabled=settings.market_data_enabled,
            selected_provider=provider if provider == MOCK_PROVIDER else ALPHA_VANTAGE,
            cache_duration_minutes=settings.cache_duration_minutes,
        )
