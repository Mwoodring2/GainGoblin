from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path

from gaingoblin.market_data.models import HistoricalPriceBar, MarketDataQuote


@dataclass(frozen=True, slots=True)
class CachedHistoricalBars:
    provider: str
    symbol: str
    lookback_days: int
    data_type: str
    fetched_at: datetime
    bars: list[HistoricalPriceBar]


@dataclass(frozen=True, slots=True)
class CachedQuote:
    provider: str
    symbol: str
    lookback_days: int
    data_type: str
    fetched_at: datetime
    quote: MarketDataQuote


class MarketDataCache:
    HISTORICAL_DAILY = "historical_daily"
    QUOTE = "quote"

    def __init__(
        self,
        path: Path,
        historical_ttl: timedelta = timedelta(hours=24),
        quote_ttl: timedelta = timedelta(minutes=5),
    ) -> None:
        self.path = Path(path)
        self.historical_ttl = historical_ttl
        self.quote_ttl = quote_ttl

    @classmethod
    def default(cls) -> MarketDataCache:
        return cls(Path("data") / "market_data_cache.json")

    def get_historical_bars(
        self,
        provider: str,
        symbol: str,
        lookback_days: int,
        now: datetime | None = None,
        *,
        allow_stale: bool = False,
    ) -> CachedHistoricalBars | None:
        return self._get_historical(
            provider,
            symbol,
            lookback_days,
            self.historical_ttl,
            now,
            allow_stale=allow_stale,
        )

    def set_historical_bars(
        self,
        provider: str,
        symbol: str,
        lookback_days: int,
        bars: list[HistoricalPriceBar],
        fetched_at: datetime | None = None,
    ) -> CachedHistoricalBars:
        fetched_at = fetched_at or datetime.now(UTC)
        symbol = symbol.upper()
        cached = CachedHistoricalBars(provider, symbol, lookback_days, self.HISTORICAL_DAILY, fetched_at, bars)
        entries = self._read()
        entries[self._cache_key(provider, symbol, lookback_days, self.HISTORICAL_DAILY)] = self._encode_historical_entry(cached)
        self._write(entries)
        return cached

    def get_quote(
        self,
        provider: str,
        symbol: str,
        now: datetime | None = None,
    ) -> CachedQuote | None:
        return self._get_quote(provider, symbol, self.quote_ttl, now)

    def set_quote(
        self,
        provider: str,
        symbol: str,
        quote: MarketDataQuote,
        fetched_at: datetime | None = None,
    ) -> CachedQuote:
        fetched_at = fetched_at or quote.fetched_at or datetime.now(UTC)
        symbol = symbol.upper()
        quote = MarketDataQuote(
            symbol=symbol,
            last_price=quote.last_price,
            day_high=quote.day_high,
            day_low=quote.day_low,
            open_price=quote.open_price,
            previous_close=quote.previous_close,
            volume=quote.volume,
            source=quote.source or provider,
            fetched_at=fetched_at,
            freshness_label=quote.freshness_label,
            bid_price=quote.bid_price,
            ask_price=quote.ask_price,
        )
        cached = CachedQuote(provider, symbol, 0, self.QUOTE, fetched_at, quote)
        entries = self._read()
        entries[self._cache_key(provider, symbol, 0, self.QUOTE)] = self._encode_quote_entry(cached)
        self._write(entries)
        return cached

    def clear(self) -> None:
        if self.path.exists():
            self.path.unlink()

    def _get_historical(
        self,
        provider: str,
        symbol: str,
        lookback_days: int,
        ttl: timedelta,
        now: datetime | None,
        *,
        allow_stale: bool = False,
    ) -> CachedHistoricalBars | None:
        entries = self._matching_entries(provider, symbol, lookback_days, self.HISTORICAL_DAILY)
        decoded = [self._decode_historical_entry(entry) for entry in entries]
        matches = [entry for entry in decoded if entry is not None]
        if not matches:
            return None
        latest = max(matches, key=lambda entry: entry.fetched_at)
        if not allow_stale and self._is_stale(latest.fetched_at, ttl, now):
            return None
        return latest

    def _get_quote(
        self,
        provider: str,
        symbol: str,
        ttl: timedelta,
        now: datetime | None,
    ) -> CachedQuote | None:
        entries = self._matching_entries(provider, symbol, 0, self.QUOTE)
        decoded = [self._decode_quote_entry(entry) for entry in entries]
        matches = [entry for entry in decoded if entry is not None]
        if not matches:
            return None
        latest = max(matches, key=lambda entry: entry.fetched_at)
        if self._is_stale(latest.fetched_at, ttl, now):
            return None
        return latest

    def _matching_entries(self, provider: str, symbol: str, lookback_days: int, data_type: str) -> list[dict]:
        symbol = symbol.upper()
        return [
            entry
            for entry in self._read().values()
            if entry.get("provider") == provider
            and entry.get("symbol") == symbol
            and int(entry.get("lookback_days", 0)) == lookback_days
            and entry.get("data_type") == data_type
        ]

    @staticmethod
    def _is_stale(fetched_at: datetime, ttl: timedelta, now: datetime | None) -> bool:
        now = now or datetime.now(UTC)
        return now - fetched_at > ttl

    @staticmethod
    def _cache_key(provider: str, symbol: str, lookback_days: int, data_type: str) -> str:
        return f"{provider}|{symbol.upper()}|{data_type}|{lookback_days}"

    def _read(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def _write(self, entries: dict[str, dict]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(entries, indent=2), encoding="utf-8")

    @staticmethod
    def _encode_historical_entry(cached: CachedHistoricalBars) -> dict:
        return {
            "provider": cached.provider,
            "symbol": cached.symbol,
            "lookback_days": cached.lookback_days,
            "data_type": cached.data_type,
            "fetched_at": cached.fetched_at.isoformat(),
            "bars": [
                {
                    "symbol": bar.symbol,
                    "date": bar.date.isoformat(),
                    "open_price": str(bar.open_price),
                    "high_price": str(bar.high_price),
                    "low_price": str(bar.low_price),
                    "close_price": str(bar.close_price),
                    "volume": bar.volume,
                    "source": bar.source,
                }
                for bar in cached.bars
            ],
        }

    @staticmethod
    def _encode_quote_entry(cached: CachedQuote) -> dict:
        quote = cached.quote
        return {
            "provider": cached.provider,
            "symbol": cached.symbol,
            "lookback_days": cached.lookback_days,
            "data_type": cached.data_type,
            "fetched_at": cached.fetched_at.isoformat(),
            "quote": {
                "symbol": quote.symbol,
                "last_price": str(quote.last_price),
                "day_high": _decimal_to_string(quote.day_high),
                "day_low": _decimal_to_string(quote.day_low),
                "open_price": _decimal_to_string(quote.open_price),
                "previous_close": _decimal_to_string(quote.previous_close),
                "bid_price": _decimal_to_string(quote.bid_price),
                "ask_price": _decimal_to_string(quote.ask_price),
                "volume": quote.volume,
                "source": quote.source,
                "freshness_label": quote.freshness_label,
            },
        }

    @staticmethod
    def _decode_historical_entry(entry: dict) -> CachedHistoricalBars | None:
        try:
            fetched_at = _parse_datetime(entry["fetched_at"])
            bars = [
                HistoricalPriceBar(
                    symbol=str(raw_bar["symbol"]),
                    date=datetime.fromisoformat(raw_bar["date"]).date(),
                    open_price=Decimal(str(raw_bar["open_price"])),
                    high_price=Decimal(str(raw_bar["high_price"])),
                    low_price=Decimal(str(raw_bar["low_price"])),
                    close_price=Decimal(str(raw_bar["close_price"])),
                    volume=raw_bar.get("volume"),
                    source=str(raw_bar.get("source", "")),
                )
                for raw_bar in entry.get("bars", [])
            ]
            return CachedHistoricalBars(
                provider=str(entry["provider"]),
                symbol=str(entry["symbol"]),
                lookback_days=int(entry["lookback_days"]),
                data_type=str(entry["data_type"]),
                fetched_at=fetched_at,
                bars=bars,
            )
        except (KeyError, TypeError, ValueError):
            return None

    @staticmethod
    def _decode_quote_entry(entry: dict) -> CachedQuote | None:
        try:
            fetched_at = _parse_datetime(entry["fetched_at"])
            raw_quote = entry["quote"]
            quote = MarketDataQuote(
                symbol=str(raw_quote["symbol"]),
                last_price=Decimal(str(raw_quote["last_price"])),
                day_high=_decimal_or_none(raw_quote.get("day_high")),
                day_low=_decimal_or_none(raw_quote.get("day_low")),
                open_price=_decimal_or_none(raw_quote.get("open_price")),
                previous_close=_decimal_or_none(raw_quote.get("previous_close")),
                bid_price=_decimal_or_none(raw_quote.get("bid_price")),
                ask_price=_decimal_or_none(raw_quote.get("ask_price")),
                volume=raw_quote.get("volume"),
                source=str(raw_quote.get("source", "")),
                fetched_at=fetched_at,
                freshness_label=str(raw_quote.get("freshness_label", "unknown")),
            )
            return CachedQuote(
                provider=str(entry["provider"]),
                symbol=str(entry["symbol"]),
                lookback_days=int(entry["lookback_days"]),
                data_type=str(entry["data_type"]),
                fetched_at=fetched_at,
                quote=quote,
            )
        except (KeyError, TypeError, ValueError):
            return None


def _parse_datetime(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    return parsed


def _decimal_or_none(value: object) -> Decimal | None:
    if value in (None, ""):
        return None
    return Decimal(str(value))


def _decimal_to_string(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return str(value)


# Backward-compatible alias for earlier local drafts.
HistoricalRangeCache = MarketDataCache
