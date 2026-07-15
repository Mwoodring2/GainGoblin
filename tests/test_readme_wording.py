"""README product language must stay internally consistent."""

from __future__ import annotations

from pathlib import Path

README = Path(__file__).resolve().parents[1] / "README.md"


def test_readme_describes_manual_first_optional_market_data() -> None:
    text = README.read_text(encoding="utf-8")
    lowered = text.lower()

    assert "manual-first" in lowered or "works offline" in lowered
    assert "optionally fetch" in lowered or "optional market data" in lowered
    assert "operating-system credential store" in lowered or "credential store" in lowered
    assert "disabled by default" in lowered

    # Conflicting legacy claims must not reappear.
    assert "does not connect to brokerages, fetch live stock prices" not in lowered
    assert "all calculations are based only on values the user manually enters." not in lowered

    assert "does not connect to brokerage accounts" in lowered
    assert "recommend buying or selling" in lowered
    assert "alpha vantage" in lowered
