import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect, QSize
from PySide6.QtWidgets import QApplication

from gaingoblin import __version__
from gaingoblin.database import HoldingRepository
from gaingoblin.main_window import MainWindow
from gaingoblin.widgets.clipboard_shell import ClipboardShell
from gaingoblin.widgets.goblin_companion import GoblinCompanionWidget
from gaingoblin.widgets.holdings_table import HoldingsTable
from gaingoblin.widgets.summary_cards import SummaryCards


def _show_window(tmp_path, width: int, height: int) -> MainWindow:
    app = QApplication.instance() or QApplication([])
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    window = MainWindow(repository)
    window.resize(width, height)
    window.show()
    app.processEvents()
    return window


def test_main_window_goblin_ui_smoke(tmp_path) -> None:
    window = _show_window(tmp_path, 1024, 700)

    assert window.windowTitle() == f"Gain Goblin v{__version__}"
    shell = window.findChild(ClipboardShell)
    assert shell is not None
    assert shell.has_artwork
    assert window.findChild(GoblinCompanionWidget) is not None
    assert window.findChild(SummaryCards) is not None
    assert window.findChild(HoldingsTable) is not None

    companion = window.findChild(GoblinCompanionWidget)
    assert companion is not None
    assert companion.x() >= 0
    assert companion.y() >= 0

    window.close()


def test_main_window_stage_layout_matches_shell_geometry(tmp_path) -> None:
    for width, height in ((1024, 700), (1366, 768), (1600, 900), (1920, 1080)):
        window = _show_window(tmp_path, width, height)
        shell = window.findChild(ClipboardShell)
        assert shell is not None

        geometry = shell.stage_geometry()
        origin = geometry.content_rect.topLeft()
        assert window.summary_cards.geometry() == QRect(geometry.summary_rect).translated(-origin)
        assert window._ledger_panel.geometry() == QRect(geometry.ledger_rect).translated(-origin)
        assert window._companion_panel.geometry() == QRect(geometry.companion_rect).translated(-origin)
        assert not geometry.clip_rect.intersects(geometry.summary_rect)
        assert not geometry.clip_rect.intersects(geometry.body_rect)

        window.close()


def test_companion_has_reserved_space_and_does_not_cover_table(tmp_path) -> None:
    window = _show_window(tmp_path, 1240, 860)

    table = window.findChild(HoldingsTable)
    companion = window.findChild(GoblinCompanionWidget)
    assert table is not None
    assert companion is not None

    table_rect = QRect(table.mapTo(window, QPoint(0, 0)), table.size())
    companion_rect = QRect(companion.mapTo(window, QPoint(0, 0)), companion.size())
    assert not table_rect.intersects(companion_rect)
    assert companion.width() >= 154

    window.close()


def test_action_buttons_have_enough_width_for_labels(tmp_path) -> None:
    window = _show_window(tmp_path, 1024, 700)

    assert window.add_button.minimumWidth() >= 132
    assert window.import_button.minimumWidth() >= 180
    assert window.edit_button.minimumWidth() >= 150
    assert window.delete_button.minimumWidth() >= 160
    assert window.export_button.minimumWidth() >= 144

    window.close()


def test_main_window_resizes_without_layout_collisions(tmp_path) -> None:
    app = QApplication.instance() or QApplication([])
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    window = MainWindow(repository)
    window.show()

    for size in (QSize(1024, 700), QSize(1280, 720), QSize(1366, 768), QSize(1600, 900), QSize(1920, 1080)):
        window.resize(size)
        app.processEvents()
        shell = window.findChild(ClipboardShell)
        assert shell is not None
        geometry = shell.stage_geometry()
        assert geometry.window_rect.contains(geometry.stage_rect)
        assert geometry.paper_rect.contains(geometry.content_rect)
        assert not geometry.ledger_rect.intersects(geometry.companion_rect)

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


def test_main_window_companion_goblin_is_grounded(tmp_path) -> None:
    window = _show_window(tmp_path, 1600, 900)
    companion = window.findChild(GoblinCompanionWidget)
    assert companion is not None

    canvas = companion.goblin_canvas()
    goblin_rect = QRect(canvas.mapTo(companion, QPoint(0, 0)), canvas.size())

    assert goblin_rect.y() > companion.rect().height() * 0.35
    assert goblin_rect.bottom() >= companion.rect().height() * 0.72
    assert companion.stage_widget().floor_rect().height() > 0

    window.close()

