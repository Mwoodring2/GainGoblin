import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from gaingoblin import __version__
from gaingoblin.database import HoldingRepository
from gaingoblin.main_window import MainWindow
from gaingoblin.widgets.clipboard_shell import ClipboardShell
from gaingoblin.widgets.goblin_companion import GoblinCompanionWidget
from gaingoblin.widgets.holdings_table import HoldingsTable
from gaingoblin.widgets.summary_cards import SummaryCards


def test_main_window_goblin_ui_smoke(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    window = MainWindow(repository)

    window.show()
    app.processEvents()

    assert window.windowTitle() == f"Gain Goblin v{__version__}"
    shell = window.findChild(ClipboardShell)
    assert shell is not None
    assert shell.has_artwork
    assert window.findChild(GoblinCompanionWidget) is not None
    assert window.findChild(SummaryCards) is not None
    assert window.findChild(HoldingsTable) is not None

    window.resize(1024, 700)
    app.processEvents()

    companion = window.findChild(GoblinCompanionWidget)
    assert companion is not None
    assert companion.x() >= 0
    assert companion.y() >= 0

    window.close()


def test_clipboard_shell_preserves_art_aspect_ratio_on_large_resize(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    window = MainWindow(repository)
    shell = window.findChild(ClipboardShell)
    assert shell is not None

    window.resize(1900, 950)
    window.show()
    app.processEvents()

    art_rect = shell.art_rect()
    source_size = shell.source_size()
    assert art_rect.width() <= source_size.width()
    assert art_rect.height() <= source_size.height()
    assert abs((art_rect.width() / art_rect.height()) - (source_size.width() / source_size.height())) < 0.01

    window.close()


def test_companion_has_reserved_space_and_does_not_cover_table(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    window = MainWindow(repository)
    window.resize(1240, 860)
    window.show()
    app.processEvents()

    table = window.findChild(HoldingsTable)
    companion = window.findChild(GoblinCompanionWidget)
    assert table is not None
    assert companion is not None

    table_rect = QRect(table.mapTo(window, QPoint(0, 0)), table.size())
    companion_rect = QRect(companion.mapTo(window, QPoint(0, 0)), companion.size())
    assert not table_rect.intersects(companion_rect)
    assert companion.width() >= 188

    window.close()


def test_no_live_or_brokerage_integration_modules() -> None:
    source_root = Path(__file__).resolve().parents[1] / "src" / "gaingoblin"
    forbidden_fragments = (
        "broker",
        "price_fetch",
        "live_price",
        "trade_executor",
        "recommendation_engine",
    )
    module_names = [path.stem.lower() for path in source_root.rglob("*.py")]
    for fragment in forbidden_fragments:
        assert all(fragment not in module_name for module_name in module_names)
