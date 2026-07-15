from datetime import date
from decimal import Decimal

import pytest

from gaingoblin.market_data.errors import MalformedMarketDataError, NoMarketDataError
from gaingoblin.market_data.historical_range import calculate_historical_range_metrics
from gaingoblin.market_data.models import HistoricalPriceBar


def sample_bars() -> list[HistoricalPriceBar]:
    return [
        HistoricalPriceBar("ORC", date(2026, 1, 1), Decimal("7.00"), Decimal("7.50"), Decimal("6.90"), Decimal("7.25"), 1000000, "test"),
        HistoricalPriceBar("ORC", date(2026, 1, 2), Decimal("7.25"), Decimal("7.70"), Decimal("7.10"), Decimal("7.60"), 1100000, "test"),
        HistoricalPriceBar("ORC", date(2026, 1, 3), Decimal("7.60"), Decimal("8.00"), Decimal("7.40"), Decimal("7.90"), 1200000, "test"),
    ]


def test_historical_range_metrics() -> None:
    metrics = calculate_historical_range_metrics(sample_bars(), 90, "test", freshness_label="end-of-day")

    assert metrics.average_high == Decimal("7.733333333333333333333333333")
    assert metrics.average_low == Decimal("7.133333333333333333333333333")
    assert metrics.median_high == Decimal("7.70")
    assert metrics.median_low == Decimal("7.10")
    assert metrics.highest_high == Decimal("8.00")
    assert metrics.lowest_low == Decimal("6.90")
    assert metrics.last_close == Decimal("7.90")
    assert metrics.average_volume == Decimal("1100000")
    assert metrics.spread == Decimal("0.600000000000000000000000000")
    assert metrics.spread_percent == Decimal("7.594936708860759493670886076")
    assert metrics.freshness_label == "end-of-day"


def test_historical_range_52_week_extremes_when_lookback_is_one_year() -> None:
    metrics = calculate_historical_range_metrics(sample_bars(), 252, "test")

    assert metrics.highest_high == Decimal("8.00")
    assert metrics.lowest_low == Decimal("6.90")


def test_zero_bars_returns_friendly_error() -> None:
    with pytest.raises(NoMarketDataError):
        calculate_historical_range_metrics([], 90)


def test_invalid_negative_prices_rejected() -> None:
    bars = [
        HistoricalPriceBar("BAD", date(2026, 1, 1), Decimal("1"), Decimal("-1"), Decimal("0"), Decimal("1"), 1, "test")
    ]

    with pytest.raises(MalformedMarketDataError):
        calculate_historical_range_metrics(bars, 20)
