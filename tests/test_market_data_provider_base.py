from datetime import date
from decimal import Decimal

import pytest

from gaingoblin.market_data.errors import MissingApiKeyError
from gaingoblin.market_data.models import HistoricalPriceBar
from gaingoblin.market_data.provider_base import MarketDataProvider
from gaingoblin.market_data.providers.alpha_vantage_provider import AlphaVantageProvider
from gaingoblin.market_data.providers.mock_provider import MockProvider
from gaingoblin.market_data.providers.nasdaq_data_link_provider import NasdaqDataLinkProvider
from gaingoblin.market_data.providers.polygon_provider import PolygonProvider


def test_provider_base_requires_fetch_implementation() -> None:
    with pytest.raises(TypeError):
        MarketDataProvider()


def test_mock_provider_returns_matching_symbol_bars_and_quote() -> None:
    bars = [
        HistoricalPriceBar("ORC", date(2026, 1, 1), Decimal("7"), Decimal("8"), Decimal("6"), Decimal("7"), None, "demo"),
        HistoricalPriceBar("VTI", date(2026, 1, 1), Decimal("1"), Decimal("2"), Decimal("1"), Decimal("2"), None, "demo"),
    ]
    provider = MockProvider(bars=bars)

    assert len(provider.fetch_daily_bars("orc", 20)) == 1
    assert provider.fetch_quote("ORC").last_price == Decimal("7")
    assert provider.provider_name == "Mock"
    assert provider.supports_quotes


def test_api_providers_missing_key_return_friendly_error() -> None:
    for provider in (
        AlphaVantageProvider(api_key=""),
        PolygonProvider(api_key=""),
        NasdaqDataLinkProvider(api_key=""),
    ):
        with pytest.raises(MissingApiKeyError):
            provider.fetch_daily_bars("ORC", 90)
