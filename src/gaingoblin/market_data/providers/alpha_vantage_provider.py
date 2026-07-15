"""Alpha Vantage market-data provider (first fully implemented online provider)."""

from __future__ import annotations

import logging
import re
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from gaingoblin.market_data.errors import (
    AuthenticationError,
    MalformedMarketDataError,
    MissingApiKeyError,
    NoMarketDataError,
    RateLimitError,
    SymbolNotFoundError,
)
from gaingoblin.market_data.http import DEFAULT_TIMEOUT_SECONDS, get_json
from gaingoblin.market_data.models import HistoricalPriceBar, MarketDataQuote
from gaingoblin.market_data.provider_base import MarketDataProvider

logger = logging.getLogger(__name__)

ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
_SYMBOL_RE = re.compile(r"^[A-Z][A-Z0-9.\-]{0,11}$")


class AlphaVantageProvider(MarketDataProvider):
    """Fetch quotes and daily bars from Alpha Vantage over HTTPS.

    Free / common retail plans do not justify a ``real-time`` freshness label.
    Quotes are labeled ``delayed``; historical bars are ``end-of-day``.
    """

    provider_name = "Alpha Vantage"
    requires_api_key = True
    supports_quotes = True
    supports_historical_daily = True
    supports_realtime = False
    freshness_label = "delayed"
    supports_intraday = False
    supports_realtime_quote = False
    delay_label = freshness_label
    historical_freshness_label = "end-of-day"

    def __init__(
        self,
        api_key: str = "",
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        request_json: Callable[..., Any] | None = None,
    ) -> None:
        super().__init__(api_key)
        self.timeout_seconds = float(timeout_seconds)
        self._request_json = request_json or get_json

    def fetch_quote(self, symbol: str) -> MarketDataQuote:
        self._require_api_key()
        cleaned = self._validate_symbol(symbol)
        payload = self._request(
            {
                "function": "GLOBAL_QUOTE",
                "symbol": cleaned,
            }
        )
        quote_block = payload.get("Global Quote")
        if not isinstance(quote_block, dict) or not quote_block:
            raise SymbolNotFoundError()
        price_text = quote_block.get("05. price")
        if price_text in (None, ""):
            raise SymbolNotFoundError()
        try:
            last_price = Decimal(str(price_text))
        except (InvalidOperation, ValueError) as exc:
            raise MalformedMarketDataError() from exc
        if last_price <= 0:
            raise MalformedMarketDataError()

        fetched_at = datetime.now(UTC)
        logger.info(
            "alpha_vantage_quote_ok symbol=%s freshness=%s",
            cleaned,
            self.freshness_label,
        )
        return MarketDataQuote(
            symbol=cleaned,
            last_price=last_price,
            day_high=self._optional_decimal(quote_block.get("03. high")),
            day_low=self._optional_decimal(quote_block.get("04. low")),
            open_price=self._optional_decimal(quote_block.get("02. open")),
            previous_close=self._optional_decimal(quote_block.get("08. previous close")),
            volume=self._optional_int(quote_block.get("06. volume")),
            source=self.provider_name,
            fetched_at=fetched_at,
            freshness_label=self.freshness_label,
        )

    def fetch_daily_bars(self, symbol: str, lookback_days: int) -> list[HistoricalPriceBar]:
        self._require_api_key()
        cleaned = self._validate_symbol(symbol)
        days = max(1, int(lookback_days))
        outputsize = "compact" if days <= 100 else "full"
        payload = self._request(
            {
                "function": "TIME_SERIES_DAILY",
                "symbol": cleaned,
                "outputsize": outputsize,
            }
        )
        series = payload.get("Time Series (Daily)")
        if not isinstance(series, dict) or not series:
            raise NoMarketDataError()

        bars: list[HistoricalPriceBar] = []
        try:
            ordered_dates = sorted(series.keys(), reverse=True)
        except TypeError as exc:
            raise MalformedMarketDataError() from exc

        for date_text in ordered_dates[:days]:
            row = series.get(date_text)
            if not isinstance(row, dict):
                raise MalformedMarketDataError()
            try:
                bar_date = date.fromisoformat(str(date_text))
                open_price = Decimal(str(row["1. open"]))
                high_price = Decimal(str(row["2. high"]))
                low_price = Decimal(str(row["3. low"]))
                close_price = Decimal(str(row["4. close"]))
                volume = self._optional_int(row.get("5. volume"))
            except (KeyError, InvalidOperation, ValueError, TypeError) as exc:
                raise MalformedMarketDataError() from exc
            if min(open_price, high_price, low_price, close_price) < 0:
                raise MalformedMarketDataError()
            if high_price < low_price:
                raise MalformedMarketDataError()
            bars.append(
                HistoricalPriceBar(
                    cleaned,
                    bar_date,
                    open_price,
                    high_price,
                    low_price,
                    close_price,
                    volume,
                    self.provider_name,
                )
            )

        if not bars:
            raise NoMarketDataError()

        bars.reverse()
        logger.info(
            "alpha_vantage_bars_ok symbol=%s lookback=%s result_count=%s freshness=%s",
            cleaned,
            days,
            len(bars),
            self.historical_freshness_label,
        )
        return bars

    def _request(self, params: dict[str, str]) -> dict[str, Any]:
        query = {**params, "apikey": self.api_key}
        payload = self._request_json(
            ALPHA_VANTAGE_BASE_URL,
            params=query,
            timeout_seconds=self.timeout_seconds,
        )
        if not isinstance(payload, dict):
            raise MalformedMarketDataError()
        self._raise_for_provider_payload(payload)
        return payload

    def _require_api_key(self) -> None:
        if not self.api_key:
            raise MissingApiKeyError()

    @staticmethod
    def _validate_symbol(symbol: str) -> str:
        cleaned = str(symbol or "").strip().upper()
        if not cleaned or not _SYMBOL_RE.match(cleaned):
            raise SymbolNotFoundError()
        return cleaned

    @staticmethod
    def _raise_for_provider_payload(payload: dict[str, Any]) -> None:
        note = payload.get("Note") or payload.get("Information")
        if isinstance(note, str) and note.strip():
            lowered = note.lower()
            if "api key" in lowered and ("invalid" in lowered or "premium" in lowered):
                raise AuthenticationError()
            if "frequency" in lowered or "call frequency" in lowered or "thank you for using" in lowered:
                raise RateLimitError()
            if "premium" in lowered:
                raise RateLimitError()
            raise RateLimitError()

        error_message = payload.get("Error Message")
        if isinstance(error_message, str) and error_message.strip():
            lowered = error_message.lower()
            if "invalid api" in lowered or "apikey" in lowered or "api key" in lowered:
                raise AuthenticationError()
            raise SymbolNotFoundError()

    @staticmethod
    def _optional_decimal(value: Any) -> Decimal | None:
        if value in (None, ""):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return None

    @staticmethod
    def _optional_int(value: Any) -> int | None:
        if value in (None, ""):
            return None
        try:
            return int(Decimal(str(value)))
        except (InvalidOperation, ValueError, TypeError):
            return None
