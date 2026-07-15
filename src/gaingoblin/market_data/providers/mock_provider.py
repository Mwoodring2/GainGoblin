from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from gaingoblin.market_data.errors import NoMarketDataError
from gaingoblin.market_data.models import HistoricalPriceBar, MarketDataQuote
from gaingoblin.market_data.provider_base import MarketDataProvider


class MockProvider(MarketDataProvider):
    provider_name = "Mock"
    requires_api_key = False
    supports_quotes = True
    supports_historical_daily = True
    supports_realtime = False
    freshness_label = "end-of-day"
    delay_label = freshness_label

    def __init__(self, api_key: str = "", bars: list[HistoricalPriceBar] | None = None) -> None:
        super().__init__(api_key)
        self._bars = list(bars or [])

    def fetch_quote(self, symbol: str) -> MarketDataQuote:
        bars = self.fetch_daily_bars(symbol, 2)
        last = bars[-1]
        previous = bars[-2] if len(bars) > 1 else None
        return MarketDataQuote(
            symbol=last.symbol,
            last_price=last.close_price,
            day_high=last.high_price,
            day_low=last.low_price,
            open_price=last.open_price,
            previous_close=previous.close_price if previous is not None else None,
            volume=last.volume,
            source=self.provider_name,
            fetched_at=datetime.now(UTC),
            freshness_label=self.freshness_label,
        )

    def fetch_daily_bars(self, symbol: str, lookback_days: int) -> list[HistoricalPriceBar]:
        symbol = symbol.upper()
        bars = [bar for bar in self._bars if bar.symbol.upper() == symbol]
        if not bars and not self._bars:
            bars = self._demo_bars(symbol)
        bars = bars[-lookback_days:]
        if not bars:
            raise NoMarketDataError()
        return bars

    @staticmethod
    def _demo_bars(symbol: str) -> list[HistoricalPriceBar]:
        return [
            HistoricalPriceBar(symbol, date(2026, 1, 1), Decimal("7.00"), Decimal("7.50"), Decimal("6.90"), Decimal("7.25"), 1000000, "Mock"),
            HistoricalPriceBar(symbol, date(2026, 1, 2), Decimal("7.25"), Decimal("7.70"), Decimal("7.10"), Decimal("7.60"), 1100000, "Mock"),
            HistoricalPriceBar(symbol, date(2026, 1, 3), Decimal("7.60"), Decimal("8.00"), Decimal("7.40"), Decimal("7.90"), 1200000, "Mock"),
        ]
