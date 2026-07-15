"""Tests for market-data value provenance helpers."""

from gaingoblin.market_data.provenance import (
    ValueOrigin,
    badge_label_for_origin,
    provenance_line,
    status_badge_for_freshness,
    summary_low_high_phrase,
)


def test_badge_labels_for_origins() -> None:
    assert badge_label_for_origin(ValueOrigin.MANUAL) == "Manual"
    assert badge_label_for_origin(ValueOrigin.FETCHED_HISTORY) == "Historical"
    assert badge_label_for_origin(ValueOrigin.USER_ADJUSTED) == "Adjusted"
    assert badge_label_for_origin(ValueOrigin.FETCHED_QUOTE, "delayed") == "Delayed"
    assert badge_label_for_origin(ValueOrigin.FETCHED_QUOTE, "end-of-day") == "End-of-day"
    assert badge_label_for_origin(ValueOrigin.FETCHED_QUOTE, "real-time") == "Real-time quote"


def test_summary_phrases_by_origin() -> None:
    low, high = summary_low_high_phrase(ValueOrigin.FETCHED_HISTORY)
    assert low == "Value at fetched historical average low"
    assert high == "Value at fetched historical average high"

    low, high = summary_low_high_phrase(ValueOrigin.MANUAL)
    assert low == "Value at manually entered low"
    assert high == "Value at manually entered high"

    low, high = summary_low_high_phrase(ValueOrigin.USER_ADJUSTED)
    assert low == "Value at adjusted low"
    assert high == "Value at adjusted high"


def test_status_badges_separate_live_delayed_and_cached() -> None:
    assert status_badge_for_freshness("delayed", from_cache=False) == "DELAYED"
    assert status_badge_for_freshness("end-of-day", from_cache=False) == "END OF DAY"
    assert status_badge_for_freshness("real-time", from_cache=False) == "LIVE"
    assert status_badge_for_freshness("end-of-day", from_cache=True) == "CACHED"
    assert status_badge_for_freshness("offline cache", from_cache=True) == "OFFLINE CACHE"


def test_provenance_line_includes_provider_when_fetched() -> None:
    assert (
        provenance_line("Low", ValueOrigin.FETCHED_HISTORY, "Alpha Vantage")
        == "Low: Historical value from Alpha Vantage"
    )
    assert provenance_line("High", ValueOrigin.MANUAL) == "High: Manually entered"
