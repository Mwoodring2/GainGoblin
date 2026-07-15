from __future__ import annotations

from importlib.resources import as_file, files

from PySide6.QtCore import QRect, QSize, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget

from gaingoblin.ui.parchment_painter import draw_parchment_panel
from gaingoblin.ui.stage_geometry import (
    DESIGN_HEIGHT,
    DESIGN_WIDTH,
    StageGeometry,
    calculate_stage_geometry,
)


class ClipboardShell(QWidget):
    """Decorative clipboard stage driven by one deterministic geometry model."""

    SOURCE_SIZE = QSize(DESIGN_WIDTH, DESIGN_HEIGHT)
    MAX_RASTER_SCALE = 1.08

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ClipboardShell")
        self.setAutoFillBackground(False)
        self._wood_frame = self._load_asset("assets/premium_ui/clipboard_wood_frame.png")
        self._parchment = self._load_asset("assets/premium_ui/parchment_sheet.png")
        self._clip = self._load_asset("assets/premium_ui/clipboard_clip.png")
        self._legacy_background = self._load_asset(
            "assets/clipboard_kit/clipboard_shell_base.png"
        )
        self._background = (
            self._wood_frame if not self._wood_frame.isNull() else self._legacy_background
        )
        self._pixmap_cache: dict[tuple[str, int, int, str], QPixmap] = {}
        self._content_widget: QWidget | None = None

    @property
    def has_artwork(self) -> bool:
        return not self._background.isNull()

    @property
    def has_layered_artwork(self) -> bool:
        return (
            not self._wood_frame.isNull()
            and not self._parchment.isNull()
            and not self._clip.isNull()
        )

    def source_size(self) -> QSize:
        return QSize(self.SOURCE_SIZE)

    def stage_geometry(self) -> StageGeometry:
        return calculate_stage_geometry(self.size())

    def art_rect(self) -> QRect:
        return QRect(self.stage_geometry().board_rect)

    def parchment_rect(self) -> QRect:
        return QRect(self.stage_geometry().paper_rect)

    def content_rect(self) -> QRect:
        return QRect(self.stage_geometry().content_rect)

    def title_rect(self) -> QRect:
        return QRect(self.stage_geometry().title_rect)

    def summary_rect(self) -> QRect:
        return QRect(self.stage_geometry().summary_rect)

    def ledger_rect(self) -> QRect:
        return QRect(self.stage_geometry().ledger_rect)

    def companion_rect(self) -> QRect:
        return QRect(self.stage_geometry().companion_rect)

    def set_content_widget(self, widget: QWidget) -> None:
        widget.setParent(self)
        self._content_widget = widget
        self._position_content_widget()
        widget.show()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_content_widget()
        self.update()

    def paintEvent(self, event) -> None:
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        painter.fillRect(self.rect(), QColor("#060705"))

        geometry = self.stage_geometry()

        if not self._wood_frame.isNull():
            self._draw_cover_pixmap(painter, self._wood_frame, geometry.board_rect, "wood")
        elif not self._legacy_background.isNull():
            self._draw_contained_pixmap(
                painter, self._legacy_background, geometry.board_rect, "legacy"
            )
        else:
            painter.fillRect(geometry.board_rect, QColor("#3b2110"))

        draw_parchment_panel(
            painter, geometry.paper_rect, radius=22, border_color=QColor("#6f542c")
        )
        if not self._parchment.isNull():
            painter.save()
            painter.setOpacity(0.52)
            self._draw_cover_pixmap(painter, self._parchment, geometry.paper_rect, "paper")
            painter.restore()
            painter.setPen(QColor(94, 71, 39, 165))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(geometry.paper_rect.adjusted(1, 1, -2, -2), 22, 22)

        if not self._clip.isNull():
            self._draw_contained_pixmap(painter, self._clip, geometry.clip_rect, "clip")

        painter.end()

    def _draw_contained_pixmap(
        self, painter: QPainter, source: QPixmap, target_rect: QRect, key: str
    ) -> None:
        pixmap = self._scaled_pixmap(source, target_rect.size(), key, "contain")
        if pixmap.isNull():
            return

        target = QRect(
            target_rect.x() + (target_rect.width() - pixmap.width()) // 2,
            target_rect.y() + (target_rect.height() - pixmap.height()) // 2,
            pixmap.width(),
            pixmap.height(),
        )
        painter.drawPixmap(target, pixmap)

    def _draw_cover_pixmap(
        self, painter: QPainter, source: QPixmap, target_rect: QRect, key: str
    ) -> None:
        pixmap = self._scaled_pixmap(source, target_rect.size(), key, "cover")
        if pixmap.isNull():
            return

        target = QRect(
            target_rect.x() + (target_rect.width() - pixmap.width()) // 2,
            target_rect.y() + (target_rect.height() - pixmap.height()) // 2,
            pixmap.width(),
            pixmap.height(),
        )
        painter.save()
        painter.setClipRect(target_rect)
        painter.drawPixmap(target, pixmap)
        painter.restore()

    def _scaled_pixmap(
        self, source: QPixmap, target_size: QSize, key: str, mode: str
    ) -> QPixmap:
        if source.isNull() or target_size.isEmpty():
            return QPixmap()

        cache_key = (key, target_size.width(), target_size.height(), mode)
        if cache_key in self._pixmap_cache:
            return self._pixmap_cache[cache_key]

        if mode == "cover":
            scale = max(
                target_size.width() / source.width(),
                target_size.height() / source.height(),
            )
        else:
            scale = min(
                target_size.width() / source.width(),
                target_size.height() / source.height(),
            )

        scale = min(scale, self.MAX_RASTER_SCALE)
        scaled_size = QSize(
            max(1, round(source.width() * scale)),
            max(1, round(source.height() * scale)),
        )
        if scaled_size == source.size():
            pixmap = source
        else:
            pixmap = source.scaled(
                scaled_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )

        self._pixmap_cache[cache_key] = pixmap
        return pixmap

    def _position_content_widget(self) -> None:
        if self._content_widget is None:
            return

        self._content_widget.setGeometry(self.content_rect())

    @staticmethod
    def _load_asset(relative_path: str) -> QPixmap:
        try:
            resource = files("gaingoblin").joinpath(relative_path)
            with as_file(resource) as path:
                return QPixmap(str(path))
        except (FileNotFoundError, ModuleNotFoundError):
            return QPixmap()
