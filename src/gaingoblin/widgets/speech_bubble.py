from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout


class SpeechBubble(QFrame):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("SpeechBubble")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        self._label = QLabel("Goblin tally ready.")
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(self._label)

        self.setStyleSheet(
            """
            QFrame#SpeechBubble {
                background-color: #202818;
                border: 1px solid #e0b84f;
                border-radius: 12px;
            }
            QLabel {
                color: #f3ead2;
                font-size: 12px;
            }
            """
        )

    def set_text(self, text: str) -> None:
        self._label.setText(text)
