from __future__ import annotations

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPainterPath, QPen


def draw_parchment_panel(
    painter: QPainter,
    rect: QRect,
    *,
    radius: int = 18,
    border_color: QColor | None = None,
) -> None:
    if rect.isNull() or rect.width() <= 0 or rect.height() <= 0:
        return

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    bounds = QRectF(rect).adjusted(0.5, 0.5, -0.5, -0.5)
    path = QPainterPath()
    path.addRoundedRect(bounds, radius, radius)

    gradient = QLinearGradient(bounds.topLeft(), bounds.bottomLeft())
    gradient.setColorAt(0.0, QColor("#efd9aa"))
    gradient.setColorAt(0.52, QColor("#e4c891"))
    gradient.setColorAt(1.0, QColor("#d6b77a"))
    painter.fillPath(path, gradient)

    painter.setClipPath(path)
    painter.setPen(Qt.PenStyle.NoPen)
    for index in range(120):
        x = rect.left() + ((index * 47) % max(1, rect.width()))
        y = rect.top() + ((index * 83) % max(1, rect.height()))
        alpha = 18 + (index % 4) * 5
        painter.setBrush(QColor(116, 86, 45, alpha))
        painter.drawEllipse(x, y, 1 + (index % 2), 1 + ((index + 1) % 2))

    painter.setClipping(False)

    edge = border_color or QColor("#806338")
    painter.setPen(QPen(edge, 2))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)

    inner = QRectF(bounds).adjusted(7, 7, -7, -7)
    inner_path = QPainterPath()
    inner_path.addRoundedRect(inner, max(2, radius - 6), max(2, radius - 6))
    painter.setPen(QPen(QColor(255, 242, 201, 75), 1))
    painter.drawPath(inner_path)

    painter.restore()
