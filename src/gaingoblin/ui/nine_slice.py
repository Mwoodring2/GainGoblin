from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SliceMargins:
    left: int
    top: int
    right: int
    bottom: int


def clamp_slice_margin(value: int, maximum: int) -> int:
    return max(0, min(value, maximum))
