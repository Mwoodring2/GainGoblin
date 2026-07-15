import os
from datetime import date
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gaingoblin.market_data.cache import MarketDataCache
from gaingoblin.market_data.errors import MissingApiKeyError, NetworkUnavailableError
from gaingoblin.market_data.models import HistoricalPriceBar, MarketDataQuote
from gaingoblin.market_data.provenance import ValueOrigin
from gaingoblin.market_data.provider_base import MarketDataProvider
from gaingoblin.market_data.secret_store import MemorySecretStore
from gaingoblin.market_data.settings import MarketDataSettingsStore
from gaingoblin.widgets.range_calculator_dialog import MARKET_DATA_WARNING, RangeCalculatorDialog


class FakeProvider(MarketDataProvider):
    provider_name = "Fake"
    supports_quotes = True
    supports_historical_daily = True
    requires_api_key = False
    freshness_label = "end-of-day"

    def __init__(self, fail: bool = False, bar_count: int = 3) -> None:
        super().__init__("")
        self.fail = fail
        self.bar_count = bar_count
        self.calls = 0
        self.quote_calls = 0

    def fetch_quote(self, symbol: str) -> MarketDataQuote:
        self.quote_calls += 1
        if self.fail:
            raise NetworkUnavailableError()
        return MarketDataQuote(
            symbol,
            Decimal("7.90"),
            day_high=Decimal("8.00"),
            day_low=Decimal("7.40"),
            open_price=Decimal("7.60"),
            previous_close=Decimal("7.60"),
            volume=1200000,
            source="Fake",
            freshness_label=self.freshness_label,
        )

    def fetch_daily_bars(self, symbol: str, lookback_days: int) -> list[HistoricalPriceBar]:
        self.calls += 1
        if self.fail:
            raise NetworkUnavailableError()
        templates = [
            HistoricalPriceBar(
                symbol, date(2026, 1, 1), Decimal("7.00"), Decimal("7.50"), Decimal("6.90"), Decimal("7.25"), 1000000, "Fake"
            ),
            HistoricalPriceBar(
                symbol, date(2026, 1, 2), Decimal("7.25"), Decimal("7.70"), Decimal("7.10"), Decimal("7.60"), 1100000, "Fake"
            ),
            HistoricalPriceBar(
                symbol, date(2026, 1, 3), Decimal("7.60"), Decimal("8.00"), Decimal("7.40"), Decimal("7.90"), 1200000, "Fake"
            ),
        ]
        bars = []
        for index in range(self.bar_count):
            template = templates[index % len(templates)]
            bars.append(
                HistoricalPriceBar(
                    symbol,
                    date(2026, 1, 1 + index),
                    template.open_price,
                    template.high_price,
                    template.low_price,
                    template.close_price,
                    template.volume,
                    "Fake",
                )
            )
        return bars


class DelayedQuoteProvider(FakeProvider):
    freshness_label = "delayed"


class MissingKeyProvider(FakeProvider):
    provider_name = "Needs Key"
    requires_api_key = True

    def fetch_quote(self, symbol: str) -> MarketDataQuote:
        raise MissingApiKeyError()

    def fetch_daily_bars(self, symbol: str, lookback_days: int) -> list[HistoricalPriceBar]:
        raise MissingApiKeyError()


def _dialog(
    tmp_path,
    provider: MarketDataProvider | None = None,
    *,
    secret_store: MemorySecretStore | None = None,
) -> RangeCalculatorDialog:
    secrets = secret_store or MemorySecretStore()
    store = MarketDataSettingsStore(tmp_path / "settings.json", secret_store=secrets)
    return RangeCalculatorDialog(
        market_data_provider=provider,
        market_data_cache=MarketDataCache(tmp_path / "cache.json"),
        settings_store=store,
        secret_store=secrets,
    )


def test_fetched_values_can_populate_range_calculator_fields(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    provider = FakeProvider()
    dialog = _dialog(tmp_path, provider)
    dialog.symbol_name.setText("ORC")
    dialog.shares.setText("100")
    dialog.planned_buy_price.setText("7.50")

    metrics = dialog.fetch_market_numbers()

    assert metrics is not None
    assert dialog.average_low_price.text() in {"", "0", "0.0000"}
    assert dialog.apply_range_button.isEnabled()
    assert dialog.history_average_low_value.text() == "7.1333"
    assert dialog.history_average_high_value.text() == "7.7333"
    assert dialog.history_bars_value.text() == "3"
    assert "END OF DAY" in dialog.quote_freshness_badge.text()
    assert "END OF DAY" in dialog.freshness_value.text()
    assert "trading days" in dialog.lookback_value.text()
    assert dialog.cache_status_value.text() in {"Live fetch", "Cached"}

    dialog.apply_fetched_range()
    assert dialog.average_low_price.text() == "7.1333"
    assert dialog.average_high_price.text() == "7.7333"
    assert dialog.current_price.text() == "7.9000"
    assert dialog.week_52_low.text() == "6.9000"
    assert dialog.week_52_high.text() == "8.0000"
    assert dialog.average_volume.text() == "1,100,000"
    assert dialog._field_origins["average_low_price"] is ValueOrigin.FETCHED_HISTORY
    assert dialog._field_origins["current_price"] is ValueOrigin.FETCHED_QUOTE
    assert dialog._field_badges["average_low_price"].text() == "Historical"
    assert dialog._field_badges["current_price"].text() == "End-of-day"

    result = dialog.calculate_current_scenario()
    assert result is not None
    assert result.symbol_name == "ORC"

    dialog.close()


def test_manual_fields_remain_editable_after_fetch(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, FakeProvider())
    dialog.symbol_name.setText("ORC")

    assert dialog.fetch_market_numbers() is not None
    dialog.apply_fetched_range()
    dialog.average_low_price.setText("6.5000")
    dialog.average_high_price.setText("9.2500")

    assert not dialog.average_low_price.isReadOnly()
    assert dialog.average_low_price.text() == "6.5000"
    assert dialog.average_high_price.text() == "9.2500"
    assert dialog._field_origins["average_low_price"] is ValueOrigin.USER_ADJUSTED
    assert dialog._field_badges["average_high_price"].text() == "Adjusted"

    dialog.close()


def test_fetch_failure_is_handled_without_crashing_or_erasing_manual_values(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, FakeProvider(fail=True))
    dialog.symbol_name.setText("ORC")
    dialog.average_low_price.setText("6.50")
    dialog.average_high_price.setText("9.25")

    assert dialog.fetch_market_numbers() is None
    assert "Internet connection failed." in dialog.status_label.text()
    assert dialog.average_low_price.text() == "6.50"
    assert dialog.average_high_price.text() == "9.25"

    dialog.close()


def test_refresh_failure_preserves_cached_values_and_inputs(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    provider = FakeProvider()
    dialog = _dialog(tmp_path, provider)
    dialog.symbol_name.setText("ORC")
    dialog.shares.setText("100")
    dialog.planned_buy_price.setText("7.50")
    assert dialog.fetch_market_numbers() is not None
    dialog.apply_fetched_range()
    prior_low = dialog.average_low_price.text()
    prior_history_low = dialog.history_average_low_value.text()
    prior_metrics = dialog.last_metrics

    dialog.market_data_cache.clear()
    provider.fail = True
    assert dialog.fetch_market_numbers() is None
    assert dialog.last_metrics is prior_metrics
    assert dialog.history_average_low_value.text() == prior_history_low
    assert dialog.average_low_price.text() == prior_low
    assert dialog.planned_buy_price.text() == "7.50"
    assert "kept" in dialog.status_label.text().lower()

    dialog.close()


def test_missing_api_key_has_friendly_error(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, MissingKeyProvider())
    dialog.symbol_name.setText("ORC")

    assert dialog.fetch_market_numbers() is None
    assert "API key is missing." in dialog.status_label.text()

    dialog.close()


def test_online_market_data_disabled_by_default_without_injected_provider(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path)
    dialog.symbol_name.setText("ORC")

    assert dialog.fetch_market_numbers() is None
    assert "setup" in dialog.status_label.text().lower() or "Market Data" in dialog.status_label.text()
    assert dialog.open_settings_button.text() == "Open Market Data Settings"

    dialog.close()


def test_fresh_cached_result_avoids_provider_daily_call_and_shows_cached_timestamp(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    provider = FakeProvider()
    cache = MarketDataCache(tmp_path / "cache.json")
    cache.set_historical_bars("Fake", "ORC", 90, provider.fetch_daily_bars("ORC", 90))
    cache.set_quote("Fake", "ORC", provider.fetch_quote("ORC"))
    provider.calls = 0
    provider.quote_calls = 0
    secrets = MemorySecretStore()
    dialog = RangeCalculatorDialog(
        market_data_provider=provider,
        market_data_cache=cache,
        settings_store=MarketDataSettingsStore(tmp_path / "settings.json", secret_store=secrets),
        secret_store=secrets,
    )
    dialog.symbol_name.setText("ORC")

    metrics = dialog.fetch_market_numbers()

    assert metrics is not None
    assert provider.calls == 0
    assert provider.quote_calls == 0
    assert "cached" in dialog.fetched_value.text().lower()
    assert "cache" in dialog.source_value.text().lower() or dialog.cache_status_value.text() == "Cached"
    assert dialog.cache_status_value.text() == "Cached"
    assert dialog.history_status_badge.text() == "CACHED"
    assert not dialog.history_cache_notice.isHidden()
    assert "Using cached historical data" in dialog.history_cache_notice.text()

    dialog.close()


def test_warning_text_does_not_contain_trade_direction_language(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, FakeProvider())

    text = dialog.market_warning.text().lower()
    forbidden = ("recommended buy", "recommended sell", "should buy", "should sell", "guaranteed", "likely profit")
    assert all(word not in text for word in forbidden)
    assert dialog.market_warning.text() == MARKET_DATA_WARNING
    assert "not predictions or recommendations" in text

    dialog.close()


def test_offline_range_calculator_still_works_without_provider(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path)
    dialog.symbol_name.setText("ORC")
    dialog.shares.setText("10")
    dialog.planned_buy_price.setText("5")
    dialog.average_low_price.setText("4")
    dialog.average_high_price.setText("8")

    result = dialog.calculate_current_scenario()
    assert result is not None
    assert result.symbol_name == "ORC"
    assert dialog._field_origins["average_low_price"] is ValueOrigin.MANUAL

    dialog.close()


def test_quote_and_history_have_separate_freshness_labels(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, DelayedQuoteProvider())
    dialog.symbol_name.setText("ORC")

    assert dialog.fetch_market_numbers() is not None
    assert dialog.quote_freshness_badge.text() == "DELAYED"
    assert dialog.history_status_badge.text() in {"DELAYED", "END OF DAY"}
    assert "Quote:" in dialog.freshness_value.text()
    assert "History:" in dialog.freshness_value.text()
    assert dialog.history_bars_value.text() == "3"
    assert dialog.quote_day_high_value.text() == "8.0000"

    dialog.close()


def test_fewer_bars_than_requested_shows_neutral_notice(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, FakeProvider(bar_count=3))
    dialog.symbol_name.setText("ORC")
    dialog.lookback_combo.setCurrentIndex(2)

    assert dialog.fetch_market_numbers() is not None
    assert dialog.history_requested_value.text() == "90 trading days"
    assert dialog.history_bars_value.text() == "3"
    assert not dialog.history_fewer_bars_notice.isHidden()
    assert "fewer historical bars" in dialog.history_fewer_bars_notice.text().lower()

    dialog.close()


def test_missing_optional_quote_metric_displays_unavailable(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])

    class SparseQuoteProvider(FakeProvider):
        def fetch_quote(self, symbol: str) -> MarketDataQuote:
            self.quote_calls += 1
            return MarketDataQuote(
                symbol,
                Decimal("7.90"),
                source="Fake",
                freshness_label="delayed",
            )

    dialog = _dialog(tmp_path, SparseQuoteProvider())
    dialog.symbol_name.setText("ORC")
    assert dialog.fetch_market_numbers() is not None
    assert dialog.quote_day_high_value.text() == "Unavailable"
    assert dialog.quote_volume_value.text() == "Unavailable"
    assert dialog.quote_day_high_value.text() != "0"
    assert dialog.quote_day_high_value.text() != "0.0000"

    dialog.close()


def test_copied_summary_uses_provenance_language(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, FakeProvider())
    dialog.symbol_name.setText("ORC")
    dialog.shares.setText("100")
    dialog.planned_buy_price.setText("7.50")
    assert dialog.fetch_market_numbers() is not None
    dialog.apply_fetched_range()
    assert dialog.calculate_current_scenario() is not None

    summary = dialog._summary_text(dialog.last_result)
    assert "Value at fetched historical average low" in summary
    assert "Value at fetched historical average high" in summary
    assert "Historical value from Fake" in summary
    assert "No brokerage sync, trade execution, prediction, recommendation" in summary

    dialog.average_high_price.setText("9.2500")
    assert dialog.calculate_current_scenario() is not None
    adjusted = dialog._summary_text(dialog.last_result)
    assert "Value at adjusted high" in adjusted

    dialog.close()


def test_copied_summary_says_manual_for_manual_values(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path)
    dialog.symbol_name.setText("ORC")
    dialog.shares.setText("10")
    dialog.planned_buy_price.setText("5")
    dialog.average_low_price.setText("4")
    dialog.average_high_price.setText("8")
    assert dialog.calculate_current_scenario() is not None

    summary = dialog._summary_text(dialog.last_result)
    assert "Value at manually entered low" in summary
    assert "Value at manually entered high" in summary

    dialog.close()
