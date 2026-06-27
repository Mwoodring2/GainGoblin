from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from gaingoblin.database import HoldingRepository
from gaingoblin.main_window import MainWindow
from gaingoblin.theme import apply_goblin_theme


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Gain Goblin")
    apply_goblin_theme(app)

    repository = HoldingRepository()
    window = MainWindow(repository)
    window.show()
    return app.exec()
