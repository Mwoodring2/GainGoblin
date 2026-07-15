from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True, init=False)
class MarketDataQuote:
    symbol: str
    last_price: Decimal
    day_high: Decimal | None
    day_low: Decimal | None
    open_price: Decimal | None
    previous_close: Decimal | None
    volume: int | None
    source: str
    fetched_at: datetime | None
    freshness_label: str
    bid_price: Decimal | None
    ask_price: Decimal | None

    def __init__(
        self,
        symbol: str,
        last_price: Decimal,
        day_high: Decimal | None = None,
        day_low: Decimal | None = None,
        open_price: Decimal | None = None,
        previous_close: Decimal | None = None,
        volume: int | None = None,
        source: str = "",
        fetched_at: datetime | None = None,
        freshness_label: str = "unknown",
        *,
        delay_label: str | None = None,
        bid_price: Decimal | None = None,
        ask_price: Decimal | None = None,
    ) -> None:
        object.__setattr__(self, "symbol", symbol.upper())
        object.__setattr__(self, "last_price", last_price)
        object.__setattr__(self, "day_high", day_high)
        object.__setattr__(self, "day_low", day_low)
        object.__setattr__(self, "open_price", open_price)
        object.__setattr__(self, "previous_close", previous_close)
        object.__setattr__(self, "volume", volume)
        object.__setattr__(self, "source", source)
        object.__setattr__(self, "fetched_at", fetched_at)
        object.__setattr__(self, "freshness_label", delay_label or freshness_label)
        object.__setattr__(self, "bid_price", bid_price)
        object.__setattr__(self, "ask_price", ask_price)

    @property
    def delay_label(self) -> str:
        return self.freshness_label


@dataclass(frozen=True, slots=True)
class HistoricalPriceBar:
    symbol: str
    date: date
    open_price: Decimal
    high_price: Decimal
    low_price: Decimal
    close_price: Decimal
    volume: int | None = None
    source: str = ""


@dataclass(frozen=True, slots=True)
class HistoricalRangeMetrics:
    symbol: str
    lookback_days: int
    bar_count: int
    start_date: date
    end_date: date
    average_high: Decimal
    average_low: Decimal
    median_high: Decimal
    median_low: Decimal
    highest_high: Decimal
    lowest_low: Decimal
    last_close: Decimal
    average_volume: Decimal | None
    spread: Decimal
    spread_percent: Decimal
    source: str
    fetched_at: datetime
    freshness_label: str = "unknown"

    @property
    def range_spread(self) -> Decimal:
        return self.spread

    @property
    def range_spread_percent(self) -> Decimal:
        return self.spread_percent

    @property
    def delay_label(self) -> str:
        return self.freshness_label


@dataclass(frozen=True, slots=True)
class MarketDataProviderStatus:
    provider_name: str
    enabled: bool
    configured: bool
    supports_quotes: bool
    supports_historical_daily: bool
    supports_realtime: bool
    requires_api_key: bool
    message: str = ""

    @property
    def supports_intraday(self) -> bool:
        return False

    @property
    def supports_realtime_quote(self) -> bool:
        return self.supports_realtime
