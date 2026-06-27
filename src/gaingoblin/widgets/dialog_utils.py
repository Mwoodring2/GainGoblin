from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QDialog, QWidget


def center_and_clamp_dialog(dialog: QDialog, parent: QWidget | None = None) -> None:
    screen = None
    if parent is not None and parent.windowHandle() is not None:
        screen = parent.windowHandle().screen()
    if screen is None:
        screen = dialog.screen()
    if screen is None:
        screen = QGuiApplication.primaryScreen()
    if screen is None:
        return

    available = screen.availableGeometry()
    max_width = int(available.width() * 0.92)
    max_height = int(available.height() * 0.88)

    dialog.resize(min(dialog.width(), max_width), min(dialog.height(), max_height))
    dialog.setMaximumSize(max_width, max_height)

    parent_rect = parent.frameGeometry() if parent is not None else available
    x = parent_rect.center().x() - dialog.width() // 2
    y = parent_rect.center().y() - dialog.height() // 2

    x = max(available.left(), min(x, available.right() - dialog.width()))
    y = max(available.top(), min(y, available.bottom() - dialog.height()))
    dialog.move(x, y)
