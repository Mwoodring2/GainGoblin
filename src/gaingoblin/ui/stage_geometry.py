from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QRect, QSize

from gaingoblin.ui.breakpoints import breakpoint_for_size

DESIGN_WIDTH = 1600
DESIGN_HEIGHT = 1000
STAGE_ASPECT = DESIGN_WIDTH / DESIGN_HEIGHT
MAX_STAGE_WIDTH = 1536
MAX_STAGE_HEIGHT = 960
WINDOW_PADDING = 12


@dataclass(frozen=True)
class StageGeometry:
    window_rect: QRect
    stage_rect: QRect
    board_rect: QRect
    paper_rect: QRect
    clip_rect: QRect
    content_rect: QRect
    title_rect: QRect
    summary_rect: QRect
    body_rect: QRect
    ledger_rect: QRect
    companion_rect: QRect
    scale: float
    breakpoint_name: str


def calculate_stage_geometry(window_size: QSize) -> StageGeometry:
    window_rect = QRect(0, 0, max(1, window_size.width()), max(1, window_size.height()))
    available = window_rect.adjusted(
        WINDOW_PADDING,
        WINDOW_PADDING,
        -WINDOW_PADDING,
        -WINDOW_PADDING,
    )
    if available.width() <= 0 or available.height() <= 0:
        available = window_rect

    stage_width = min(available.width(), MAX_STAGE_WIDTH)
    stage_height = round(stage_width / STAGE_ASPECT)
    max_height = min(available.height(), MAX_STAGE_HEIGHT)
    if stage_height > max_height:
        stage_height = max(1, max_height)
        stage_width = round(stage_height * STAGE_ASPECT)

    stage_rect = QRect(
        available.x() + (available.width() - stage_width) // 2,
        available.y() + (available.height() - stage_height) // 2,
        max(1, stage_width),
        max(1, stage_height),
    )
    scale = stage_rect.width() / DESIGN_WIDTH
    breakpoint = breakpoint_for_size(stage_rect.width(), stage_rect.height())

    board_rect = QRect(stage_rect)

    def s(value: int) -> int:
        return max(1, round(value * scale))

    paper_inset_x = max(s(112), 64)
    paper_top = max(s(132), 74)
    paper_bottom = max(s(58), 34)
    paper_rect = QRect(
        stage_rect.x() + paper_inset_x,
        stage_rect.y() + paper_top,
        max(1, stage_rect.width() - paper_inset_x * 2),
        max(1, stage_rect.height() - paper_top - paper_bottom),
    )

    clip_width = min(s(600), round(stage_rect.width() * 0.43))
    clip_height = max(1, round(clip_width / 2.83))
    clip_rect = QRect(
        stage_rect.center().x() - clip_width // 2,
        stage_rect.y() + max(s(16), 8),
        clip_width,
        clip_height,
    )

    content_inset_x = max(s(30), 20)
    content_bottom = max(s(30), 20)
    content_left = paper_rect.x() + content_inset_x
    content_right = paper_rect.right() - content_inset_x

    gap_small = max(s(14), 10)
    gap_medium = max(s(22), 14)
    title_height = max(s(58), 42)
    title_y = max(
        paper_rect.y() + max(s(64), 42),
        clip_rect.bottom() + gap_small,
    )
    title_rect = QRect(
        content_left,
        title_y,
        max(1, content_right - content_left + 1),
        title_height,
    )

    summary_height = max(s(110), 166 if breakpoint.compact else 100)
    summary_rect = QRect(
        content_left,
        title_rect.bottom() + gap_medium,
        title_rect.width(),
        summary_height,
    )

    body_top = summary_rect.bottom() + max(s(24), 16)
    body_bottom = paper_rect.bottom() - content_bottom
    if body_bottom <= body_top:
        body_bottom = paper_rect.bottom()
    body_rect = QRect(
        content_left,
        body_top,
        title_rect.width(),
        max(1, body_bottom - body_top + 1),
    )

    body_gap = max(s(24), 14)
    companion_ratio = 0.23 if breakpoint.compact else 0.25
    min_companion = max(s(190), 154 if breakpoint.compact else 216)
    max_companion = max(s(340), min_companion)
    companion_width = min(
        max_companion,
        max(min_companion, round(body_rect.width() * companion_ratio)),
    )
    if body_rect.width() - companion_width - body_gap < max(s(560), 420):
        companion_width = max(
            min_companion,
            body_rect.width() - body_gap - max(s(560), 420),
        )
    companion_width = max(1, min(companion_width, body_rect.width() - body_gap - 1))
    ledger_width = max(1, body_rect.width() - companion_width - body_gap)
    ledger_rect = QRect(body_rect.x(), body_rect.y(), ledger_width, body_rect.height())
    companion_rect = QRect(
        ledger_rect.right() + body_gap + 1,
        body_rect.y(),
        companion_width,
        body_rect.height(),
    )

    content_rect = QRect(
        content_left,
        title_rect.y(),
        title_rect.width(),
        max(1, body_rect.bottom() - title_rect.y() + 1),
    )

    return StageGeometry(
        window_rect=window_rect,
        stage_rect=stage_rect,
        board_rect=board_rect,
        paper_rect=paper_rect,
        clip_rect=clip_rect,
        content_rect=content_rect,
        title_rect=title_rect,
        summary_rect=summary_rect,
        body_rect=body_rect,
        ledger_rect=ledger_rect,
        companion_rect=companion_rect,
        scale=scale,
        breakpoint_name=breakpoint.name,
    )
