"""Value provenance for market-populated Range Calculator fields."""

from __future__ import annotations

from enum import StrEnum


class ValueOrigin(StrEnum):
    """Where a calculator field value came from."""

    MANUAL = "manual"
    FETCHED_QUOTE = "fetched_quote"
    FETCHED_HISTORY = "fetched_history"
    USER_ADJUSTED = "user_adjusted"


BADGE_TOOLTIPS: dict[str, str] = {
    "Manual": "Entered manually by you.",
    "Historical": "Calculated from historical daily price bars.",
    "Delayed": "Fetched quote may be delayed based on provider access.",
    "Real-time quote": "Fetched quote marked real-time by the provider plan.",
    "End-of-day": "Fetched end-of-day market data.",
    "Adjusted": "Originally fetched, then edited manually.",
}


def badge_label_for_origin(origin: ValueOrigin, freshness_label: str = "") -> str:
    """Return a compact UI badge for ``origin`` and optional freshness."""
    if origin is ValueOrigin.MANUAL:
        return "Manual"
    if origin is ValueOrigin.USER_ADJUSTED:
        return "Adjusted"
    if origin is ValueOrigin.FETCHED_HISTORY:
        return "Historical"
    lowered = (freshness_label or "").strip().lower()
    if "real-time" in lowered or "realtime" in lowered or lowered == "live":
        return "Real-time quote"
    if "end-of-day" in lowered or "end of day" in lowered or lowered == "eod":
        return "End-of-day"
    return "Delayed"


def summary_low_high_phrase(origin: ValueOrigin) -> tuple[str, str]:
    """Return (low phrase, high phrase) for copied summaries."""
    if origin is ValueOrigin.FETCHED_HISTORY:
        return (
            "Value at fetched historical average low",
            "Value at fetched historical average high",
        )
    if origin is ValueOrigin.USER_ADJUSTED:
        return ("Value at adjusted low", "Value at adjusted high")
    return ("Value at manually entered low", "Value at manually entered high")


def provenance_line(field_label: str, origin: ValueOrigin, provider: str = "") -> str:
    """Human-readable provenance line for summaries."""
    provider_text = f" from {provider}" if provider else ""
    if origin is ValueOrigin.FETCHED_HISTORY:
        return f"{field_label}: Historical value{provider_text}"
    if origin is ValueOrigin.FETCHED_QUOTE:
        return f"{field_label}: Quote value{provider_text}"
    if origin is ValueOrigin.USER_ADJUSTED:
        return f"{field_label}: Adjusted after fetch"
    return f"{field_label}: Manually entered"


def status_badge_for_freshness(freshness_label: str, *, from_cache: bool) -> str:
    """Return LIVE / DELAYED / END OF DAY / CACHED / OFFLINE CACHE."""
    if from_cache:
        lowered = (freshness_label or "").strip().lower()
        if lowered in {"cached", "offline cache", "stale"}:
            return "OFFLINE CACHE"
        return "CACHED"
    lowered = (freshness_label or "").strip().lower()
    if "real-time" in lowered or "realtime" in lowered or lowered == "live":
        return "LIVE"
    if "end-of-day" in lowered or "end of day" in lowered or lowered == "eod":
        return "END OF DAY"
    if "delay" in lowered:
        return "DELAYED"
    if lowered in {"cached", "offline cache"}:
        return "CACHED"
    return "DELAYED"
