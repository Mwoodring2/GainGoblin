"""Alpha Vantage provider tests use mocked HTTP only — no network access."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from typing import Any

import pytest

from gaingoblin.market_data.cache import MarketDataCache
from gaingoblin.market_data.errors import (
    AuthenticationError,
    MalformedMarketDataError,
    MissingApiKeyError,
    NetworkUnavailableError,
    NoMarketDataError,
    ProviderTimeoutError,
    RateLimitError,
    SymbolNotFoundError,
)
from gaingoblin.market_data.providers.alpha_vantage_provider import AlphaVantageProvider


def _quote_payload(symbol: str = "ORC", price: str = "7.90") -> dict[str, Any]:
    return {
        "Global Quote": {
            "01. symbol": symbol,
            "02. open": "7.60",
            "03. high": "8.00",
            "04. low": "7.40",
            "05. price": price,
            "06. volume": "1200000",
            "08. previous close": "7.60",
        }
    }


def _bars_payload() -> dict[str, Any]:
    return {
        "Meta Data": {"2. Symbol": "ORC"},
        "Time Series (Daily)": {
            "2026-01-03": {
                "1. open": "7.60",
                "2. high": "8.00",
                "3. low": "7.40",
                "4. close": "7.90",
                "5. volume": "1200000",
            },
            "2026-01-02": {
                "1. open": "7.25",
                "2. high": "7.70",
                "3. low": "7.10",
                "4. close": "7.60",
                "5. volume": "1100000",
            },
            "2026-01-01": {
                "1. open": "7.00",
                "2. high": "7.50",
                "3. low": "6.90",
                "4. close": "7.25",
                "5. volume": "1000000",
            },
        },
    }


class FakeHttp:
    def __init__(self, responses: list[Any] | None = None, error: Exception | None = None) -> None:
        self.responses = list(responses or [])
        self.error = error
        self.calls: list[dict[str, str]] = []

    def __call__(self, url: str, *, params: dict[str, str] | None = None, **_kwargs: Any) -> Any:
        assert "apikey" not in url.lower()
        self.calls.append(dict(params or {}))
        if self.error is not None:
            raise self.error
        if not self.responses:
            raise AssertionError("No mocked responses remaining")
        return self.responses.pop(0)


def test_successful_quote_response_is_delayed_freshness() -> None:
    http = FakeHttp([_quote_payload()])
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)

    quote = provider.fetch_quote("orc")

    assert quote.symbol == "ORC"
    assert quote.last_price == Decimal("7.90")
    assert quote.freshness_label == "delayed"
    assert quote.source == "Alpha Vantage"
    assert provider.supports_realtime is False
    assert "demo-key" not in repr(provider)


def test_successful_historical_bars_response_is_end_of_day_path() -> None:
    http = FakeHttp([_bars_payload()])
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)

    bars = provider.fetch_daily_bars("ORC", 2)

    assert len(bars) == 2
    assert bars[0].date == date(2026, 1, 2)
    assert bars[-1].close_price == Decimal("7.90")
    assert provider.historical_freshness_label == "end-of-day"


def test_invalid_symbol_raises() -> None:
    provider = AlphaVantageProvider(api_key="demo-key", request_json=FakeHttp([]))
    with pytest.raises(SymbolNotFoundError):
        provider.fetch_quote("!!!")


def test_missing_api_key_raises() -> None:
    provider = AlphaVantageProvider(api_key="")
    with pytest.raises(MissingApiKeyError):
        provider.fetch_quote("ORC")


def test_authentication_failure() -> None:
    http = FakeHttp([{"Error Message": "Invalid API call. Please retry or check apikey."}])
    provider = AlphaVantageProvider(api_key="bad-key", request_json=http)
    with pytest.raises(AuthenticationError):
        provider.fetch_quote("ORC")


def test_rate_limit() -> None:
    http = FakeHttp(
        [{"Note": "Thank you for using Alpha Vantage! Our standard API call frequency is 25."}]
    )
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)
    with pytest.raises(RateLimitError):
        provider.fetch_quote("ORC")


def test_timeout() -> None:
    http = FakeHttp(error=ProviderTimeoutError())
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)
    with pytest.raises(ProviderTimeoutError):
        provider.fetch_quote("ORC")


def test_network_unavailable() -> None:
    http = FakeHttp(error=NetworkUnavailableError())
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)
    with pytest.raises(NetworkUnavailableError):
        provider.fetch_daily_bars("ORC", 20)


def test_malformed_json_payload() -> None:
    http = FakeHttp(["not-a-dict"])
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)
    with pytest.raises(MalformedMarketDataError):
        provider.fetch_quote("ORC")


def test_empty_time_series() -> None:
    http = FakeHttp([{"Time Series (Daily)": {}}])
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)
    with pytest.raises(NoMarketDataError):
        provider.fetch_daily_bars("ORC", 20)


def test_empty_global_quote_is_symbol_not_found() -> None:
    http = FakeHttp([{"Global Quote": {}}])
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)
    with pytest.raises(SymbolNotFoundError):
        provider.fetch_quote("ORC")


def test_cache_fallback_after_provider_failure(tmp_path) -> None:
    http = FakeHttp([_bars_payload()])
    provider = AlphaVantageProvider(api_key="demo-key", request_json=http)
    bars = provider.fetch_daily_bars("ORC", 3)
    cache = MarketDataCache(tmp_path / "cache.json", historical_ttl=timedelta(seconds=1))
    cache.set_historical_bars("Alpha Vantage", "ORC", 3, bars)

    stale = cache.get_historical_bars("Alpha Vantage", "ORC", 3, allow_stale=True)
    assert stale is not None
    assert len(stale.bars) == 3


def test_provider_repr_hides_api_key() -> None:
    provider = AlphaVantageProvider(api_key="very-secret-key")
    assert "very-secret-key" not in repr(provider)
