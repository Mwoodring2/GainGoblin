from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutBreakpoint:
    name: str
    compact: bool
    show_speech: bool
    goblin_size: int
    companion_width: int
    content_margin: int
    summary_columns: int
    action_button_min_width: int


def breakpoint_for_size(width: int, height: int) -> LayoutBreakpoint:
    if width < 1260 or height < 760:
        return LayoutBreakpoint(
            name="compact",
            compact=True,
            show_speech=False,
            goblin_size=156,
            companion_width=170,
            content_margin=10,
            summary_columns=2,
            action_button_min_width=132,
        )

    if width < 1450:
        return LayoutBreakpoint(
            name="standard",
            compact=False,
            show_speech=True,
            goblin_size=204,
            companion_width=232,
            content_margin=14,
            summary_columns=4,
            action_button_min_width=146,
        )

    return LayoutBreakpoint(
        name="wide",
        compact=False,
        show_speech=True,
        goblin_size=244,
        companion_width=292,
        content_margin=18,
        summary_columns=4,
        action_button_min_width=156,
    )
