import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from gaingoblin.widgets.goblin_sprite_loader import GoblinSpriteLibrary


def test_sprite_loader_does_not_crash_when_manifest_is_missing() -> None:
    app = QApplication.instance() or QApplication([])
    library = GoblinSpriteLibrary(resource_root="assets/goblin_missing")

    assert not library.available()
    assert library.animation("idle") is None


def test_sprite_loader_reads_declared_manifest_states() -> None:
    app = QApplication.instance() or QApplication([])
    library = GoblinSpriteLibrary()

    assert "idle" in library.declared_states()
    assert "holding_added" in library.declared_states()
    assert "profit_up" in library.declared_states()
    assert "profit_down" in library.declared_states()


def test_sprite_loader_tolerates_missing_listed_frames() -> None:
    app = QApplication.instance() or QApplication([])
    library = GoblinSpriteLibrary()

    assert library.animation("idle") is None or library.has_animation("idle")


def test_sprite_loader_loads_bundled_animation_frames() -> None:
    app = QApplication.instance() or QApplication([])
    library = GoblinSpriteLibrary()

    assert library.has_animation("idle")
    assert library.has_animation("holding_added")
    assert library.has_animation("profit_up")
