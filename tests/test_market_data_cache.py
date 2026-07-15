from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from gaingoblin.market_data.cache import MarketDataCache
from gaingoblin.market_data.models import HistoricalPriceBar, MarketDataQuote


def _bar(close: str = "7.25") -> HistoricalPriceBar:
    return HistoricalPriceBar("ORC", date(2026, 1, 1), Decimal("7"), Decimal("7.50"), Decimal("6.90"), Decimal(close), 100, "test")


def test_cache_hit_when_fresh(tmp_path) -> None:
    cache = MarketDataCache(tmp_path / "cache.json", historical_ttl=timedelta(hours=24))
    fetched_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    cache.set_historical_bars("test", "ORC", 90, [_bar()], fetched_at=fetched_at)

    cached = cache.get_historical_bars("test", "orc", 90, now=fetched_at + timedelta(hours=1))

    assert cached is not None
    assert cached.data_type == MarketDataCache.HISTORICAL_DAILY
    assert cached.bars[0].close_price == Decimal("7.25")


def test_cache_miss_for_missing_data(tmp_path) -> None:
    cache = MarketDataCache(tmp_path / "cache.json")

    assert cache.get_historical_bars("test", "ORC", 90) is None


def test_cache_stale_data_not_returned(tmp_path) -> None:
    cache = MarketDataCache(tmp_path / "cache.json", historical_ttl=timedelta(hours=24))
    fetched_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    cache.set_historical_bars("test", "ORC", 90, [_bar()], fetched_at=fetched_at)

    assert cache.get_historical_bars("test", "ORC", 90, now=fetched_at + timedelta(days=2)) is None


def test_cache_refresh_replaces_stale_data_with_latest(tmp_path) -> None:
    cache = MarketDataCache(tmp_path / "cache.json", historical_ttl=timedelta(days=30))
    old = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    new = datetime(2026, 1, 2, 12, 0, tzinfo=UTC)
    cache.set_historical_bars("test", "ORC", 90, [_bar("7.25")], fetched_at=old)
    cache.set_historical_bars("test", "ORC", 90, [_bar("7.90")], fetched_at=new)

    cached = cache.get_historical_bars("test", "ORC", 90, now=new + timedelta(hours=1))

    assert cached is not None
    assert cached.fetched_at == new
    assert cached.bars[0].close_price == Decimal("7.90")


def test_quote_cache_hit_and_stale(tmp_path) -> None:
    cache = MarketDataCache(tmp_path / "cache.json", quote_ttl=timedelta(minutes=5))
    fetched_at = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)
    quote = MarketDataQuote("ORC", Decimal("7.90"), source="test", fetched_at=fetched_at, freshness_label="delayed")
    cache.set_quote("test", "ORC", quote, fetched_at=fetched_at)

    fresh = cache.get_quote("test", "orc", now=fetched_at + timedelta(minutes=4))
    stale = cache.get_quote("test", "orc", now=fetched_at + timedelta(minutes=6))

    assert fresh is not None
    assert fresh.quote.last_price == Decimal("7.90")
    assert fresh.quote.freshness_label == "delayed"
    assert stale is None
