from __future__ import annotations

from importlib.resources import as_file, files

from PySide6.QtCore import QRect, QSize
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtWidgets import QWidget


class ClipboardShell(QWidget):
    """Paints the parchment clipboard art without distorting its source ratio."""

    SOURCE_SIZE = QSize(1448, 1086)
    EDGE_PADDING = 10
    MAX_SCALE = 1.0

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("ClipboardShell")
        self.setAutoFillBackground(False)
        self._background = self._load_background()
        self._content_widget: QWidget | None = None

    @property
    def has_artwork(self) -> bool:
        return not self._background.isNull()

    def source_size(self) -> QSize:
        if self.has_artwork:
            return self._background.size()
        return QSize(self.SOURCE_SIZE)

    def art_rect(self) -> QRect:
        return QRect(self._scaled_art_rect())

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
        painter.fillRect(self.rect(), QColor("#080906"))

        art_rect = self._scaled_art_rect()
        if self.has_artwork:
            painter.drawPixmap(art_rect, self._background)
        else:
            painter.fillRect(art_rect, QColor("#d5b988"))

        painter.end()

    def _scaled_art_rect(self) -> QRect:
        source = self.source_size()
        available = self.rect().adjusted(
            self.EDGE_PADDING,
            self.EDGE_PADDING,
            -self.EDGE_PADDING,
            -self.EDGE_PADDING,
        )
        if source.width() <= 0 or source.height() <= 0 or available.width() <= 0:
            return QRect()

        scale = min(
            available.width() / source.width(),
            available.height() / source.height(),
            self.MAX_SCALE,
        )
        target_width = max(1, round(source.width() * scale))
        target_height = max(1, round(source.height() * scale))
        return QRect(
            available.x() + (available.width() - target_width) // 2,
            available.y() + (available.height() - target_height) // 2,
            target_width,
            target_height,
        )

    def _position_content_widget(self) -> None:
        if self._content_widget is None:
            return

        art_rect = self._scaled_art_rect()
        if art_rect.isNull():
            self._content_widget.setGeometry(QRect())
            return

        source = self.source_size()
        scale_x = art_rect.width() / source.width()
        scale_y = art_rect.height() / source.height()
        left = max(42, round(72 * scale_x))
        right = max(42, round(72 * scale_x))
        top = max(56, round(78 * scale_y))
        bottom = max(40, round(58 * scale_y))

        self._content_widget.setGeometry(
            QRect(
                art_rect.x() + left,
                art_rect.y() + top,
                max(1, art_rect.width() - left - right),
                max(1, art_rect.height() - top - bottom),
            )
        )

    @staticmethod
    def _load_background() -> QPixmap:
        try:
            resource = files("gaingoblin").joinpath(
                "assets/clipboard_kit/clipboard_shell_base.png"
            )
            with as_file(resource) as path:
                return QPixmap(str(path))
        except (FileNotFoundError, ModuleNotFoundError):
            return QPixmap()
