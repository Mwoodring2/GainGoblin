import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QRect
from PySide6.QtWidgets import QApplication

from gaingoblin.ui.breakpoints import breakpoint_for_size
from gaingoblin.widgets.goblin_companion import GoblinCompanionWidget


def test_goblin_companion_supports_breakpoint_sizes() -> None:
    app = QApplication.instance() or QApplication([])
    companion = GoblinCompanionWidget()

    compact = breakpoint_for_size(1024, 700)
    wide = breakpoint_for_size(1800, 1000)

    companion.set_breakpoint(compact)
    assert companion.width() == compact.companion_width

    companion.set_breakpoint(wide)
    assert companion.width() == wide.companion_width


def test_goblin_companion_play_event_accepts_known_and_unknown_events() -> None:
    app = QApplication.instance() or QApplication([])
    companion = GoblinCompanionWidget()

    companion.play_event("holding_added")
    companion.play_event("import_success")
    companion.play_event("import_failed")
    companion.play_event("profit_up")
    companion.play_event("profit_down")
    companion.play_event("thinking_tap")
    companion.play_event("delete")
    companion.play_event("look_right")
    companion.play_event("greedy_sparkle")
    companion.play_event("not_a_real_event")
    companion.set_reduced_motion(True)
    companion.play_event("import_success")

    assert companion.width() > 0
    assert companion.speech_bubble().tail_height() > 0


def test_compact_mode_hides_speech_but_keeps_goblin_visible() -> None:
    app = QApplication.instance() or QApplication([])
    companion = GoblinCompanionWidget()
    compact = breakpoint_for_size(1024, 700)
    companion.set_breakpoint(compact)
    companion.resize(compact.companion_width, 360)
    companion.show()
    app.processEvents()

    assert not companion.speech_bubble().isVisible()
    assert companion.goblin_canvas().isVisible()
    assert companion.stage_widget().isVisible()

    companion.close()


def test_goblin_is_bottom_biased_inside_companion_panel() -> None:
    app = QApplication.instance() or QApplication([])
    companion = GoblinCompanionWidget()
    wide = breakpoint_for_size(1800, 1000)
    companion.set_breakpoint(wide)
    companion.resize(wide.companion_width, 460)
    companion.show()
    app.processEvents()

    canvas = companion.goblin_canvas()
    goblin_rect = QRect(canvas.mapTo(companion, QPoint(0, 0)), canvas.size())
    assert goblin_rect.y() > companion.rect().height() * 0.35
    assert goblin_rect.bottom() >= companion.rect().height() * 0.75

    companion.close()
