import os
from importlib.resources import as_file, files

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSize
from PySide6.QtGui import QImage
from PySide6.QtWidgets import QApplication

from gaingoblin.ui.stage_geometry import MAX_STAGE_HEIGHT, MAX_STAGE_WIDTH, calculate_stage_geometry
from gaingoblin.widgets.clipboard_shell import ClipboardShell

STAGE_SIZES = [
    QSize(1024, 700),
    QSize(1280, 720),
    QSize(1366, 768),
    QSize(1600, 900),
    QSize(1920, 1080),
]


def test_stage_geometry_stays_inside_window_at_common_sizes() -> None:
    for size in STAGE_SIZES:
        geometry = calculate_stage_geometry(size)

        assert geometry.window_rect.contains(geometry.stage_rect)
        assert geometry.stage_rect.contains(geometry.paper_rect)
        assert geometry.paper_rect.contains(geometry.content_rect)
        assert geometry.content_rect.contains(geometry.title_rect)
        assert geometry.content_rect.contains(geometry.summary_rect)
        assert geometry.content_rect.contains(geometry.body_rect)


def test_stage_geometry_keeps_clip_clear_of_interactive_zones() -> None:
    for size in STAGE_SIZES:
        geometry = calculate_stage_geometry(size)

        assert not geometry.clip_rect.intersects(geometry.summary_rect)
        assert not geometry.clip_rect.intersects(geometry.body_rect)


def test_stage_geometry_body_splits_ledger_and_companion() -> None:
    for size in STAGE_SIZES:
        geometry = calculate_stage_geometry(size)

        assert geometry.body_rect.contains(geometry.ledger_rect)
        assert geometry.body_rect.contains(geometry.companion_rect)
        assert geometry.content_rect.contains(geometry.companion_rect)
        assert not geometry.ledger_rect.intersects(geometry.companion_rect)
        companion_ratio = geometry.companion_rect.width() / geometry.body_rect.width()
        assert 0.18 <= companion_ratio <= 0.30


def test_stage_geometry_caps_fullscreen_stage_size() -> None:
    geometry = calculate_stage_geometry(QSize(2560, 1440))

    assert geometry.stage_rect.width() <= MAX_STAGE_WIDTH
    assert geometry.stage_rect.height() <= MAX_STAGE_HEIGHT
    assert geometry.scale <= 1


def test_clipboard_shell_uses_stage_geometry_contract() -> None:
    app = QApplication.instance() or QApplication([])
    shell = ClipboardShell()
    shell.resize(1920, 1080)

    geometry = shell.stage_geometry()

    assert shell.art_rect() == geometry.board_rect
    assert shell.parchment_rect() == geometry.paper_rect
    assert shell.content_rect() == geometry.content_rect
    assert shell.summary_rect() == geometry.summary_rect
    assert shell.ledger_rect() == geometry.ledger_rect
    assert shell.companion_rect() == geometry.companion_rect


def test_clipboard_shell_loads_layered_premium_artwork() -> None:
    app = QApplication.instance() or QApplication([])
    shell = ClipboardShell()

    assert shell.has_layered_artwork


def test_premium_layer_backgrounds_are_cut_out() -> None:
    clip_resource = files("gaingoblin").joinpath("assets/premium_ui/clipboard_clip.png")
    wood_resource = files("gaingoblin").joinpath("assets/premium_ui/clipboard_wood_frame.png")

    with as_file(clip_resource) as clip_path, as_file(wood_resource) as wood_path:
        clip = QImage(str(clip_path))
        wood = QImage(str(wood_path))

    assert clip.pixelColor(clip.width() // 2, clip.height() // 5).alpha() == 0
    assert wood.pixelColor(10, wood.height() // 2).alpha() == 0
    assert wood.pixelColor(wood.width() - 10, wood.height() // 2).alpha() == 0
