from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from statistics import median

from gaingoblin.market_data.errors import MalformedMarketDataError, NoMarketDataError
from gaingoblin.market_data.models import HistoricalPriceBar, HistoricalRangeMetrics

ZERO = Decimal("0")
ONE_HUNDRED = Decimal("100")


def calculate_historical_range_metrics(
    bars: list[HistoricalPriceBar],
    lookback_days: int,
    source: str | None = None,
    fetched_at: datetime | None = None,
    freshness_label: str = "unknown",
    *,
    delay_label: str | None = None,
) -> HistoricalRangeMetrics:
    if not bars:
        raise NoMarketDataError()

    sorted_bars = sorted(bars, key=lambda bar: bar.date)
    _validate_bars(sorted_bars)
    count = Decimal(len(sorted_bars))
    highs = [bar.high_price for bar in sorted_bars]
    lows = [bar.low_price for bar in sorted_bars]
    volumes = [bar.volume for bar in sorted_bars if bar.volume is not None]

    average_high = sum(highs, ZERO) / count
    average_low = sum(lows, ZERO) / count
    median_high = Decimal(str(median(highs)))
    median_low = Decimal(str(median(lows)))
    highest_high = max(highs)
    lowest_low = min(lows)
    last_close = sorted_bars[-1].close_price
    average_volume = None
    if volumes:
        average_volume = Decimal(sum(volumes)) / Decimal(len(volumes))

    spread = average_high - average_low
    spread_percent = ZERO
    if last_close > ZERO:
        spread_percent = spread / last_close * ONE_HUNDRED

    return HistoricalRangeMetrics(
        symbol=sorted_bars[-1].symbol.upper(),
        lookback_days=lookback_days,
        bar_count=len(sorted_bars),
        start_date=sorted_bars[0].date,
        end_date=sorted_bars[-1].date,
        average_high=average_high,
        average_low=average_low,
        median_high=median_high,
        median_low=median_low,
        highest_high=highest_high,
        lowest_low=lowest_low,
        last_close=last_close,
        average_volume=average_volume,
        spread=spread,
        spread_percent=spread_percent,
        source=source or sorted_bars[-1].source,
        fetched_at=fetched_at or datetime.now(UTC),
        freshness_label=delay_label or freshness_label,
    )


def _validate_bars(bars: list[HistoricalPriceBar]) -> None:
    for bar in bars:
        prices = (bar.open_price, bar.high_price, bar.low_price, bar.close_price)
        if any(price < ZERO for price in prices):
            raise MalformedMarketDataError()
        if bar.high_price < bar.low_price:
            raise MalformedMarketDataError()
        if bar.volume is not None and bar.volume < 0:
            raise MalformedMarketDataError()
