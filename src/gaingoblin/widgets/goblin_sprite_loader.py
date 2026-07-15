from __future__ import annotations

import json
from dataclasses import dataclass
from importlib.resources import as_file, files

from PySide6.QtGui import QPixmap


@dataclass(frozen=True)
class SpriteAnimation:
    name: str
    frames: tuple[QPixmap, ...]
    fps: int
    loop: bool
    return_to: str | None = None


class GoblinSpriteLibrary:
    def __init__(
        self,
        package: str = "gaingoblin",
        resource_root: str = "assets/goblin",
        manifest_name: str = "manifest.json",
    ) -> None:
        self._package = package
        self._resource_root = resource_root
        self._manifest_name = manifest_name
        self._animations: dict[str, SpriteAnimation] = {}
        self._declared_states: tuple[str, ...] = ()
        self._load()

    def available(self) -> bool:
        return any(animation.frames for animation in self._animations.values())

    def animation(self, name: str) -> SpriteAnimation | None:
        return self._animations.get(name)

    def has_animation(self, name: str) -> bool:
        animation = self.animation(name)
        return animation is not None and bool(animation.frames)

    def available_states(self) -> tuple[str, ...]:
        return tuple(self._animations)

    def declared_states(self) -> tuple[str, ...]:
        return self._declared_states

    def _load(self) -> None:
        try:
            root = files(self._package).joinpath(self._resource_root)
            manifest_resource = root.joinpath(self._manifest_name)
            if not manifest_resource.is_file():
                return
            manifest = json.loads(manifest_resource.read_text(encoding="utf-8"))
        except (FileNotFoundError, ModuleNotFoundError, json.JSONDecodeError, OSError):
            return

        states = manifest.get("states", {})
        if not isinstance(states, dict):
            return
        self._declared_states = tuple(str(name) for name in states)
        default_fps = int(manifest.get("default_fps", 6) or 6)

        for name, config in states.items():
            if not isinstance(config, dict):
                continue
            frames = self._load_frames(root, config.get("frames", ()))
            if not frames:
                continue
            self._animations[str(name)] = SpriteAnimation(
                name=str(name),
                frames=tuple(frames),
                fps=max(1, int(config.get("fps", default_fps) or default_fps)),
                loop=bool(config.get("loop", True)),
                return_to=(
                    str(config["return_to"]) if config.get("return_to") is not None else None
                ),
            )

    @staticmethod
    def _load_frames(root, frame_paths) -> list[QPixmap]:
        frames: list[QPixmap] = []
        if not isinstance(frame_paths, list):
            return frames
        for relative_path in frame_paths:
            try:
                resource = root.joinpath(str(relative_path))
                if not resource.is_file():
                    continue
                with as_file(resource) as path:
                    pixmap = QPixmap(str(path))
                if not pixmap.isNull():
                    frames.append(pixmap)
            except (FileNotFoundError, OSError):
                continue
        return frames
