"""Abstract market-data provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from gaingoblin.market_data.models import (
    HistoricalPriceBar,
    MarketDataProviderStatus,
    MarketDataQuote,
)


class MarketDataProvider(ABC):
    """Provider interface for optional online market data."""

    provider_name: str = "Market Data Provider"
    requires_api_key: bool = False
    supports_quotes: bool = False
    supports_historical_daily: bool = False
    supports_realtime: bool = False
    freshness_label: str = "unknown"

    # Compatibility aliases for older local drafts.
    supports_intraday: bool = False
    supports_realtime_quote: bool = False
    delay_label: str = "unknown"

    def __init__(self, api_key: str = "") -> None:
        self._api_key = str(api_key or "")
        if self.delay_label == "unknown" and self.freshness_label != "unknown":
            self.delay_label = self.freshness_label
        if self.freshness_label == "unknown" and self.delay_label != "unknown":
            self.freshness_label = self.delay_label

    @property
    def api_key(self) -> str:
        return self._api_key

    def status(self, enabled: bool = True) -> MarketDataProviderStatus:
        configured = bool(self.api_key) or not self.requires_api_key
        message = "" if configured else "API key is missing."
        if not enabled:
            message = "Online market data is disabled."
        return MarketDataProviderStatus(
            provider_name=self.provider_name,
            enabled=enabled,
            configured=configured,
            supports_quotes=self.supports_quotes,
            supports_historical_daily=self.supports_historical_daily,
            supports_realtime=self.supports_realtime,
            requires_api_key=self.requires_api_key,
            message=message,
        )

    @abstractmethod
    def fetch_quote(self, symbol: str) -> MarketDataQuote:
        raise NotImplementedError

    @abstractmethod
    def fetch_daily_bars(self, symbol: str, lookback_days: int) -> list[HistoricalPriceBar]:
        raise NotImplementedError

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"provider_name={self.provider_name!r}, "
            f"requires_api_key={self.requires_api_key}, "
            f"configured={bool(self.api_key) or not self.requires_api_key})"
        )
