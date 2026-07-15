from __future__ import annotations

import logging
import sys

from PySide6.QtWidgets import QApplication

from gaingoblin.database import HoldingRepository
from gaingoblin.logging_config import configure_logging
from gaingoblin.main_window import MainWindow
from gaingoblin.theme import apply_goblin_theme

logger = logging.getLogger(__name__)


def main() -> int:
    configure_logging()
    logger.info("Gain Goblin starting")
    app = QApplication(sys.argv)
    app.setApplicationName("Gain Goblin")
    apply_goblin_theme(app)

    repository = HoldingRepository()
    window = MainWindow(repository)
    window.show()
    logger.info("Main window shown")
    return app.exec()
