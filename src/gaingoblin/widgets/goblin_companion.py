from __future__ import annotations

import random
from importlib.resources import as_file, files

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QBrush, QColor, QFont, QPainter, QPen, QPixmap, QPolygon
from PySide6.QtWidgets import QSizePolicy, QWidget

from gaingoblin.ui.breakpoints import LayoutBreakpoint, breakpoint_for_size
from gaingoblin.widgets.goblin_animation import ANIMATION_CLIPS, EVENT_TO_STATE, GoblinAnimationClip
from gaingoblin.widgets.goblin_sprite_loader import GoblinSpriteLibrary, SpriteAnimation
from gaingoblin.widgets.speech_bubble import SpeechBubble


class GoblinCanvas(QWidget):
    def __init__(
        self,
        parent=None,
        display_size: int = 204,
        sprite_library: GoblinSpriteLibrary | None = None,
    ) -> None:
        super().__init__(parent)
        self._frame = 0
        self._base_mood = "idle"
        self._event_state: str | None = None
        self._event_frames_remaining = 0
        self._event_return_to: str | None = None
        self._reduced_motion = False
        self._timer_interval_ms = 180
        self._sprite_library = sprite_library or GoblinSpriteLibrary()
        self._sprite_sheet = self._load_sprite_sheet()
        self.set_display_size(display_size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_display_size(self, display_size: int) -> None:
        self.setFixedSize(display_size, display_size)
        self.updateGeometry()
        self.update()

    def set_mood(self, mood: str) -> None:
        self.set_animation_state(mood)

    def set_animation_state(self, state_name: str) -> None:
        if state_name in {"idle", "happy", "greedy", "worried", "thinking"}:
            self._base_mood = state_name
            self.update()

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = enabled
        if enabled:
            self._event_state = None
            self._event_frames_remaining = 0
            self._event_return_to = None
        self.update()

    def play_state(self, state_name: str, timer_interval_ms: int) -> None:
        self._timer_interval_ms = max(1, timer_interval_ms)
        if self._reduced_motion:
            state_name = "blink"

        animation = self._sprite_library.animation(state_name)
        clip = ANIMATION_CLIPS.get(state_name)
        if animation is None and clip is None:
            return

        self._event_state = state_name
        self._event_return_to = animation.return_to if animation is not None else None
        duration_ms = self._duration_for_state(state_name, animation, clip)
        self._event_frames_remaining = max(1, duration_ms // self._timer_interval_ms)
        self.update()

    def step(self) -> None:
        self._frame = (self._frame + 1) % 960
        if self._event_frames_remaining > 0:
            self._event_frames_remaining -= 1
            if self._event_frames_remaining == 0:
                if self._event_return_to is not None:
                    self.set_animation_state(self._event_return_to)
                self._event_state = None
                self._event_return_to = None
        self.update()

    def paintEvent(self, event) -> None:
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)

        if self._paint_manifest_sprite(painter):
            self._paint_overlays(painter)
            painter.end()
            return

        if not self._sprite_sheet.isNull():
            self._paint_sprite_sheet(painter)
            self._paint_overlays(painter)
            painter.end()
            return

        self._paint_fallback(painter)
        painter.end()

    def _active_state(self) -> str:
        return self._event_state if self._event_state is not None else self._base_mood

    def _active_mood(self) -> str:
        clip = self._active_clip()
        return clip.mood

    def _active_clip(self) -> GoblinAnimationClip:
        return ANIMATION_CLIPS.get(self._active_state(), ANIMATION_CLIPS.get(self._base_mood, ANIMATION_CLIPS["idle"]))

    def _duration_for_state(
        self,
        state_name: str,
        animation: SpriteAnimation | None,
        clip: GoblinAnimationClip | None,
    ) -> int:
        if animation is not None and not animation.loop:
            return max(len(animation.frames) * self._timer_interval_ms, round((len(animation.frames) / animation.fps) * 1000))
        if clip is not None:
            return clip.duration_ms
        return ANIMATION_CLIPS.get(state_name, ANIMATION_CLIPS["idle"]).duration_ms

    def _motion_offset(self) -> int:
        clip = self._active_clip()
        if self._reduced_motion:
            return 0
        if clip.bounce_strength:
            return -clip.bounce_strength if self._frame % 8 < 4 else 0
        return 2 if self._frame % 16 < 8 else 0

    def _paint_manifest_sprite(self, painter: QPainter) -> bool:
        animation = self._sprite_library.animation(self._active_state())
        if animation is None or not animation.frames:
            return False

        frame_step = max(1, round(1000 / max(1, animation.fps * self._timer_interval_ms)))
        if animation.loop:
            frame_index = (self._frame // frame_step) % len(animation.frames)
        else:
            elapsed = max(0, len(animation.frames) - self._event_frames_remaining)
            frame_index = min(len(animation.frames) - 1, elapsed // frame_step)
        pixmap = animation.frames[frame_index]
        self._draw_pixmap_bottom_center(painter, pixmap, QRect(0, 0, self.width(), self.height()))
        return True

    def _draw_pixmap_bottom_center(self, painter: QPainter, pixmap: QPixmap, bounds: QRect) -> None:
        if pixmap.isNull():
            return
        scale = min(bounds.width() / pixmap.width(), bounds.height() / pixmap.height(), 1.0)
        target_width = max(1, round(pixmap.width() * scale))
        target_height = max(1, round(pixmap.height() * scale))
        scaled = pixmap
        if scaled.width() != target_width or scaled.height() != target_height:
            scaled = pixmap.scaled(
                QSize(target_width, target_height),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
        target = QRect(
            bounds.center().x() - scaled.width() // 2,
            bounds.bottom() - scaled.height() + 1,
            scaled.width(),
            scaled.height(),
        )
        painter.drawPixmap(target, scaled)

    def _paint_fallback(self, painter: QPainter) -> None:
        painter.scale(self.width() / 148, self.height() / 148)
        mood = self._active_mood()
        clip = self._active_clip()
        bob = self._motion_offset()
        cx = 74
        cy = 62 + bob

        green = QColor("#8ccf5f")
        dark_green = QColor("#4f7f34")
        gold = QColor("#e0b84f")
        ink = QColor("#11140f")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 70))
        painter.drawEllipse(28, 113, 78, 12)

        painter.setBrush(QBrush(dark_green))
        painter.setPen(QPen(ink, 2))
        painter.drawPolygon(QPolygon([QPoint(cx - 34, cy - 10), QPoint(cx - 64, cy - 28), QPoint(cx - 42, cy + 10)]))
        painter.drawPolygon(QPolygon([QPoint(cx + 34, cy - 10), QPoint(cx + 64, cy - 28), QPoint(cx + 42, cy + 10)]))

        painter.setBrush(QBrush(green))
        painter.setPen(QPen(ink, 2))
        painter.drawEllipse(cx - 38, cy - 36, 76, 68)

        painter.setBrush(QBrush(dark_green))
        painter.drawEllipse(cx - 7, cy - 4, 14, 10)

        painter.setBrush(QBrush(ink))
        eye_shift = clip.eye_shift
        if mood == "worried":
            painter.drawEllipse(cx - 21, cy - 12, 8, 8)
            painter.drawEllipse(cx + 13, cy - 12, 8, 8)
            painter.drawArc(cx - 14, cy + 17, 28, 16, 0, 180 * 16)
        elif mood == "greedy":
            painter.setBrush(QBrush(gold))
            painter.drawEllipse(cx - 24, cy - 15, 12, 12)
            painter.drawEllipse(cx + 12, cy - 15, 12, 12)
            painter.setBrush(QBrush(ink))
            if clip.coin_jiggle and self._frame % 6 < 3:
                eye_shift += 2
            painter.drawEllipse(cx - 20 + eye_shift, cy - 11, 4, 4)
            painter.drawEllipse(cx + 16 + eye_shift, cy - 11, 4, 4)
            painter.drawArc(cx - 17, cy + 4, 34, 22, 180 * 16, 180 * 16)
        elif mood == "thinking":
            painter.drawLine(cx - 25, cy - 13, cx - 12, cy - 9)
            painter.drawLine(cx + 12, cy - 9, cx + 25, cy - 13)
            painter.drawEllipse(cx - 19 + eye_shift, cy - 8, 6, 6)
            painter.drawEllipse(cx + 13 + eye_shift, cy - 8, 6, 6)
            painter.drawLine(cx - 10, cy + 14, cx + 10, cy + 14)
            painter.setFont(QFont("Segoe UI", 15, QFont.Weight.Bold))
            painter.drawText(cx + 32, cy - 26, "?")
        elif mood == "happy":
            painter.drawEllipse(cx - 22 + eye_shift, cy - 14, 8, 8)
            painter.drawEllipse(cx + 14 + eye_shift, cy - 14, 8, 8)
            painter.drawArc(cx - 18, cy + 2, 36, 24, 180 * 16, 180 * 16)
        else:
            blink = clip.blink and self._frame in (0, 1)
            if blink:
                painter.drawLine(cx - 23, cy - 10, cx - 13, cy - 10)
                painter.drawLine(cx + 13, cy - 10, cx + 23, cy - 10)
            else:
                painter.drawEllipse(cx - 22 + eye_shift, cy - 14, 8, 8)
                painter.drawEllipse(cx + 14 + eye_shift, cy - 14, 8, 8)
            painter.drawArc(cx - 14, cy + 4, 28, 18, 180 * 16, 180 * 16)

        painter.setBrush(QBrush(QColor("#202818")))
        painter.setPen(QPen(ink, 2))
        shoulder_offset = 2 if clip.foot_tap and self._frame % 8 < 4 else 0
        painter.drawRoundedRect(cx - 28, cy + 30 + shoulder_offset, 56, 46, 12, 12)

        coin_y = cy + 44
        coin_x = cx + 18
        if clip.coin_jiggle and not self._reduced_motion:
            coin_x += 3 if self._frame % 6 < 3 else -2
            coin_y -= 2 if self._frame % 8 < 4 else 0

        painter.setBrush(QBrush(gold))
        painter.setPen(QPen(QColor("#a8733a"), 2))
        painter.drawEllipse(coin_x, coin_y, 22, 22)

        if clip.sweat:
            painter.setBrush(QColor("#62a8d9"))
            painter.setPen(QPen(QColor("#205a84"), 1))
            painter.drawEllipse(cx + 30, cy - 8, 7, 12)

        if clip.sparkle:
            painter.setPen(QPen(gold, 2))
            for sx, sy in ((cx - 46, cy - 42), (cx + 42, cy - 36), (cx + 44, cy + 48)):
                pulse = 2 if self._frame % 8 < 4 else 0
                painter.drawLine(sx - 4 - pulse, sy, sx + 4 + pulse, sy)
                painter.drawLine(sx, sy - 4 - pulse, sx, sy + 4 + pulse)

    def _paint_sprite_sheet(self, painter: QPainter) -> None:
        frames = {
            "idle": (0, 1),
            "happy": (1, 2),
            "greedy": (2, 1),
            "worried": (3,),
            "blink": (0,),
            "look_left": (0,),
            "look_right": (1,),
            "foot_tap": (3, 0),
            "coin_jiggle": (2, 1),
            "happy_bounce": (1, 2),
            "greedy_sparkle": (2, 1),
            "worried_sweat": (3,),
            "thinking_tap": (3, 0),
            "shoulder_bob": (1, 2),
            "thinking": (3, 0),
            "holding_added": (1, 2),
            "import_success": (2, 1),
            "import_failed": (3,),
            "profit_up": (1, 2),
            "profit_down": (3,),
            "missing_targets": (3, 0),
            "delete": (3, 0),
            "celebrate": (2, 1),
        }
        state = self._active_state()
        mood = self._active_mood()
        frame_choices = frames.get(state, frames.get(mood, frames["idle"]))
        frame_index = frame_choices[(self._frame // 6) % len(frame_choices)]
        source_width = self._sprite_sheet.width() // 2
        source_height = self._sprite_sheet.height() // 2
        source = QRect(
            (frame_index % 2) * source_width,
            (frame_index // 2) * source_height,
            source_width,
            source_height,
        )
        bob = self._motion_offset()
        target = QRect(8, 4 + bob, self.width() - 16, self.height() - 12)
        painter.drawPixmap(target, self._sprite_sheet, source)

    def _paint_overlays(self, painter: QPainter) -> None:
        clip = self._active_clip()
        if not clip.sweat and not clip.sparkle and not clip.coin_jiggle:
            return
        scale = self.width() / 148
        painter.save()
        painter.scale(scale, scale)
        if clip.sweat:
            painter.setBrush(QColor("#62a8d9"))
            painter.setPen(QPen(QColor("#205a84"), 1))
            painter.drawEllipse(106, 48, 7, 12)
        if clip.sparkle:
            painter.setPen(QPen(QColor("#e0b84f"), 2))
            for sx, sy in ((34, 34), (108, 40), (112, 106)):
                pulse = 2 if self._frame % 8 < 4 else 0
                painter.drawLine(sx - 4 - pulse, sy, sx + 4 + pulse, sy)
                painter.drawLine(sx, sy - 4 - pulse, sx, sy + 4 + pulse)
        painter.restore()

    @staticmethod
    def _load_sprite_sheet() -> QPixmap:
        try:
            resource = files("gaingoblin").joinpath("assets/gain_goblin_sprite_sheet.png")
            with as_file(resource) as path:
                return QPixmap(str(path))
        except (FileNotFoundError, ModuleNotFoundError):
            return QPixmap()


class GoblinStageWidget(QWidget):
    def __init__(
        self,
        parent=None,
        display_size: int = 204,
        sprite_library: GoblinSpriteLibrary | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("GoblinStageWidget")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self._grounded = True
        self._floor_height = 38
        self._bottom_padding = 18
        self._canvas = GoblinCanvas(self, display_size, sprite_library=sprite_library)

    def canvas(self) -> GoblinCanvas:
        return self._canvas

    def set_display_size(self, display_size: int) -> None:
        self._canvas.set_display_size(display_size)
        self._position_canvas()
        self.update()

    def set_grounded(self, enabled: bool = True) -> None:
        self._grounded = enabled
        self.update()

    def set_animation_state(self, state_name: str) -> None:
        self._canvas.set_animation_state(state_name)

    def set_mood(self, mood: str) -> None:
        self._canvas.set_mood(mood)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._canvas.set_reduced_motion(enabled)

    def play_state(self, state_name: str, timer_interval_ms: int) -> None:
        self._canvas.play_state(state_name, timer_interval_ms)

    def floor_rect(self) -> QRect:
        width = max(72, round(self.width() * 0.72))
        y = self.height() - self._bottom_padding - self._floor_height
        return QRect((self.width() - width) // 2, max(0, y), width, self._floor_height)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_canvas()

    def paintEvent(self, event) -> None:
        del event
        if not self._grounded:
            return
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        floor = self.floor_rect()
        shadow = QRect(
            floor.x() + round(floor.width() * 0.12),
            floor.y() + 2,
            round(floor.width() * 0.76),
            max(8, round(floor.height() * 0.42)),
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(28, 20, 13, 125))
        painter.drawEllipse(shadow)

        plank = QRect(floor.x(), floor.y() + round(floor.height() * 0.35), floor.width(), max(8, round(floor.height() * 0.34)))
        painter.setBrush(QColor(76, 45, 22, 190))
        painter.setPen(QPen(QColor(126, 82, 41, 180), 1))
        painter.drawRoundedRect(plank, 5, 5)
        painter.setPen(QPen(QColor(36, 22, 12, 150), 1))
        painter.drawLine(plank.left() + 10, plank.center().y(), plank.right() - 10, plank.center().y())

        painter.setBrush(QColor("#e0b84f"))
        painter.setPen(QPen(QColor("#946e27"), 1))
        coin_y = plank.y() - 3
        for offset in (0, 13, 25):
            painter.drawEllipse(plank.right() - 42 + offset // 3, coin_y + offset % 7, 10, 6)
        painter.end()

    def _position_canvas(self) -> None:
        floor = self.floor_rect()
        x = (self.width() - self._canvas.width()) // 2
        y = max(0, floor.y() - self._canvas.height() + round(floor.height() * 0.75))
        self._canvas.move(x, y)


class GoblinCompanionWidget(QWidget):
    TIMER_INTERVAL_MS = 180

    def __init__(self, parent=None, random_source: random.Random | None = None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("GoblinCompanionWidget")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)
        self._breakpoint = breakpoint_for_size(1200, 800)
        self._reduced_motion = False
        self._random = random_source or random.Random()

        self._speech = SpeechBubble(self)
        self._speech.setMaximumWidth(self._breakpoint.companion_width)
        self._stage = GoblinStageWidget(self, self._breakpoint.goblin_size)

        self.set_breakpoint(self._breakpoint)

        self._timer = QTimer(self)
        self._timer.setInterval(self.TIMER_INTERVAL_MS)
        self._timer.timeout.connect(self._stage.canvas().step)
        self._timer.start()

        self._idle_timer = QTimer(self)
        self._idle_timer.timeout.connect(self._play_idle_variety)
        self._reset_idle_timer()
        self._idle_timer.start()

    def set_breakpoint(self, breakpoint: LayoutBreakpoint) -> None:
        self._breakpoint = breakpoint
        self._speech.setVisible(breakpoint.show_speech)
        self._speech.setMaximumWidth(breakpoint.companion_width)
        self._stage.set_display_size(breakpoint.goblin_size)
        self.setFixedWidth(breakpoint.companion_width)
        self._position_children()
        self.updateGeometry()

    def set_compact(self, compact: bool) -> None:
        self.set_breakpoint(breakpoint_for_size(1000 if compact else 1200, 700 if compact else 800))

    def set_stage_size(self, width: int, height: int) -> None:
        self.resize(width, height)
        self._position_children()

    def set_grounded(self, enabled: bool = True) -> None:
        self._stage.set_grounded(enabled)

    def set_reduced_motion(self, enabled: bool) -> None:
        self._reduced_motion = enabled
        self._stage.set_reduced_motion(enabled)

    def play_event(self, event_name: str) -> None:
        state_name = EVENT_TO_STATE.get(event_name)
        if state_name is None:
            return
        self.set_animation_state(state_name)

    def set_animation_state(self, state_name: str) -> None:
        self._stage.play_state(state_name, self.TIMER_INTERVAL_MS)
        self._reset_idle_timer()

    def sizeHint(self) -> QSize:
        speech_height = 64 if self._breakpoint.show_speech else 0
        return QSize(
            self._breakpoint.companion_width,
            self._breakpoint.goblin_size + speech_height + 100,
        )

    def speech_bubble(self) -> SpeechBubble:
        return self._speech

    def stage_widget(self) -> GoblinStageWidget:
        return self._stage

    def goblin_canvas(self) -> GoblinCanvas:
        return self._stage.canvas()

    def set_mood(self, mood: str) -> None:
        self._stage.set_mood(mood)

    def set_speech(self, text: str) -> None:
        self._speech.set_text(text)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._position_children()

    def _position_children(self) -> None:
        width = max(1, self.width())
        height = max(1, self.height())
        padding = max(8, round(width * 0.045))

        speech_visible = self._breakpoint.show_speech
        speech_height = max(48, min(72, round(height * 0.16))) if speech_visible else 0

        stage_min_height = self._breakpoint.goblin_size + 74
        available_for_stage = max(1, height - padding * 2 - (speech_height + padding if speech_visible else 0))
        stage_height = min(
            available_for_stage,
            max(stage_min_height, round(height * (0.66 if speech_visible else 0.86))),
        )
        stage_y = height - stage_height - padding
        stage_width = max(1, width - padding * 2)
        self._stage.setGeometry(padding, max(padding, stage_y), stage_width, stage_height)

        if speech_visible:
            bubble_gap = max(4, padding // 2)
            speech_width = min(width - padding * 2, max(120, self._breakpoint.companion_width - padding * 2))
            speech_x = (width - speech_width) // 2
            speech_y = max(padding, self._stage.y() - speech_height - bubble_gap)
            self._speech.setGeometry(speech_x, speech_y, speech_width, speech_height)
        else:
            self._speech.setGeometry(0, 0, 0, 0)

    def _play_idle_variety(self) -> None:
        if not self._reduced_motion:
            self.set_animation_state(
                self._random.choice(("blink", "look_left", "look_right", "coin_jiggle", "foot_tap", "shoulder_bob"))
            )
        self._reset_idle_timer()

    def _reset_idle_timer(self) -> None:
        self._idle_timer.setInterval(self._random.randint(5000, 12000))
