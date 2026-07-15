from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QPixmap


def scaled_pixmap_crisp(source: QPixmap, target_size: QSize) -> QPixmap:
    if source.isNull() or target_size.isEmpty():
        return QPixmap()

    source_size = source.size()
    if target_size.width() >= source_size.width() or target_size.height() >= source_size.height():
        return source

    return source.scaled(
        target_size,
        Qt.AspectRatioMode.KeepAspectRatio,
        Qt.TransformationMode.SmoothTransformation,
    )
