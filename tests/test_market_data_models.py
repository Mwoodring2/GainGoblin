from datetime import UTC, date, datetime
from decimal import Decimal

from gaingoblin.market_data.models import (
    HistoricalPriceBar,
    MarketDataProviderStatus,
    MarketDataQuote,
)


def test_market_data_models_use_decimal_prices() -> None:
    quote = MarketDataQuote(
        "ORC",
        Decimal("7.25"),
        source="test",
        fetched_at=datetime.now(UTC),
        freshness_label="delayed",
    )
    bar = HistoricalPriceBar("ORC", date(2026, 1, 1), Decimal("7.00"), Decimal("7.50"), Decimal("6.90"), Decimal("7.25"))
    status = MarketDataProviderStatus(
        provider_name="Mock",
        enabled=True,
        configured=True,
        supports_quotes=True,
        supports_historical_daily=True,
        supports_realtime=False,
        requires_api_key=False,
    )

    assert quote.last_price == Decimal("7.25")
    assert quote.freshness_label == "delayed"
    assert bar.high_price == Decimal("7.50")
    assert status.provider_name == "Mock"
    assert status.supports_quotes
