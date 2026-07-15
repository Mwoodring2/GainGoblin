import os
from datetime import date
from decimal import Decimal

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gaingoblin.market_data.cache import MarketDataCache
from gaingoblin.market_data.errors import MissingApiKeyError, NetworkUnavailableError
from gaingoblin.market_data.models import HistoricalPriceBar, MarketDataQuote
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

    def __init__(self, fail: bool = False) -> None:
        super().__init__("")
        self.fail = fail
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
        return [
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
    assert dialog.average_low_price.text() == "7.1333"
    assert dialog.average_high_price.text() == "7.7333"
    assert dialog.current_price.text() == "7.9000"
    assert dialog.week_52_low.text() == "6.9000"
    assert dialog.week_52_high.text() == "8.0000"
    assert dialog.average_volume.text() == "1,100,000"
    assert dialog.freshness_value.text() == "end-of-day"
    assert "trading days" in dialog.lookback_value.text()
    assert dialog.cache_status_value.text() in {"Live fetch", "Cached"}
    result = dialog.calculate_current_scenario()
    assert result is not None
    assert result.symbol_name == "ORC"

    dialog.close()


def test_manual_fields_remain_editable_after_fetch(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, FakeProvider())
    dialog.symbol_name.setText("ORC")

    assert dialog.fetch_market_numbers() is not None
    dialog.average_low_price.setText("6.5000")
    dialog.average_high_price.setText("9.2500")

    assert not dialog.average_low_price.isReadOnly()
    assert dialog.average_low_price.text() == "6.5000"
    assert dialog.average_high_price.text() == "9.2500"

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
    assert "cached" in dialog.fetched_value.text()
    assert "cache" in dialog.source_value.text()
    assert dialog.cache_status_value.text() == "Cached"

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

    dialog.close()


def test_freshness_and_cache_status_are_displayed(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    dialog = _dialog(tmp_path, FakeProvider())
    dialog.symbol_name.setText("ORC")

    assert dialog.fetch_market_numbers() is not None
    assert dialog.freshness_value.text() == "end-of-day"
    assert dialog.cache_status_value.text()
    assert dialog.lookback_value.text()

    dialog.close()
