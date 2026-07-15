"""Nasdaq Data Link provider placeholder — not implemented in v0.1.8-alpha."""

from __future__ import annotations

from gaingoblin.market_data.errors import MissingApiKeyError, ProviderUnavailableError
from gaingoblin.market_data.models import HistoricalPriceBar, MarketDataQuote
from gaingoblin.market_data.provider_base import MarketDataProvider


class NasdaqDataLinkProvider(MarketDataProvider):
    """Reserved Nasdaq Data Link adapter.

    This provider remains intentionally unavailable until a dedicated
    implementation ships. Prefer Alpha Vantage for online fetches.
    """

    provider_name = "Nasdaq Data Link"
    requires_api_key = True
    supports_quotes = False
    supports_historical_daily = True
    supports_realtime = False
    freshness_label = "unknown"
    delay_label = freshness_label

    def fetch_quote(self, symbol: str) -> MarketDataQuote:
        if not self.api_key:
            raise MissingApiKeyError()
        raise ProviderUnavailableError()

    def fetch_daily_bars(self, symbol: str, lookback_days: int) -> list[HistoricalPriceBar]:
        if not self.api_key:
            raise MissingApiKeyError()
        raise ProviderUnavailableError()
