from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPolygon
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class SpeechBubble(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SpeechBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
        self._tail_height = 10
        self._tail_offset = 0

        self._label = QLabel("Goblin tally ready.")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8 + self._tail_height)
        layout.addWidget(self._label)

        self.setStyleSheet(
            """
            QLabel {
                color: #f3ead2;
                font-size: 12px;
            }
            """
        )

    def set_text(self, text: str) -> None:
        self._label.setText(text)

    def set_tail_offset(self, offset: int) -> None:
        self._tail_offset = offset
        self.update()

    def tail_height(self) -> int:
        return self._tail_height

    def paintEvent(self, event) -> None:
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        bubble_rect = QRect(self.rect()).adjusted(0, 0, -1, -self._tail_height - 1)
        if bubble_rect.height() < 8:
            bubble_rect = QRect(self.rect()).adjusted(0, 0, -1, -1)

        background = QColor("#202818")
        border = QColor("#e0b84f")
        painter.setPen(QPen(border, 1))
        painter.setBrush(background)
        painter.drawRoundedRect(bubble_rect, 12, 12)

        center_x = max(
            bubble_rect.left() + 18,
            min(bubble_rect.right() - 18, bubble_rect.center().x() + self._tail_offset),
        )
        tail = QPolygon(
            [
                QPoint(center_x - 9, bubble_rect.bottom() - 1),
                QPoint(center_x + 9, bubble_rect.bottom() - 1),
                QPoint(center_x, self.rect().bottom() - 1),
            ]
        )
        painter.drawPolygon(tail)
        painter.end()
