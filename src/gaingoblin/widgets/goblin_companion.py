from __future__ import annotations

from importlib.resources import as_file, files

from PySide6.QtCore import QPoint, QRect, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QPainter, QPen, QBrush, QPixmap, QPolygon
from PySide6.QtWidgets import QSizePolicy, QVBoxLayout, QWidget

from gaingoblin.widgets.speech_bubble import SpeechBubble


class GoblinCanvas(QWidget):
    def __init__(self, parent=None, display_size: int = 224) -> None:
        super().__init__(parent)
        self._frame = 0
        self._mood = "idle"
        self._sprite_sheet = self._load_sprite_sheet()
        self.set_display_size(display_size)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

    def set_display_size(self, display_size: int) -> None:
        self.setFixedSize(display_size, display_size)
        self.updateGeometry()
        self.update()

    def set_mood(self, mood: str) -> None:
        self._mood = mood
        self.update()

    def step(self) -> None:
        self._frame = (self._frame + 1) % 24
        self.update()

    def paintEvent(self, event) -> None:
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        if not self._sprite_sheet.isNull():
            self._paint_sprite(painter)
            painter.end()
            return

        painter.scale(self.width() / 148, self.height() / 148)
        bob = 2 if self._frame % 12 < 6 else 0
        cx = 74
        cy = 62 + bob

        green = QColor("#8ccf5f")
        dark_green = QColor("#4f7f34")
        gold = QColor("#e0b84f")
        ink = QColor("#11140f")

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 80))
        painter.drawEllipse(30, 112, 72, 12)

        painter.setBrush(QBrush(dark_green))
        painter.setPen(QPen(ink, 2))
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(cx - 34, cy - 10),
                    QPoint(cx - 62, cy - 28),
                    QPoint(cx - 42, cy + 10),
                ]
            )
        )
        painter.drawPolygon(
            QPolygon(
                [
                    QPoint(cx + 34, cy - 10),
                    QPoint(cx + 62, cy - 28),
                    QPoint(cx + 42, cy + 10),
                ]
            )
        )

        painter.setBrush(QBrush(green))
        painter.setPen(QPen(ink, 2))
        painter.drawEllipse(cx - 38, cy - 36, 76, 68)

        painter.setBrush(QBrush(dark_green))
        painter.drawEllipse(cx - 7, cy - 4, 14, 10)

        painter.setBrush(QBrush(ink))
        if self._mood == "worried":
            painter.drawEllipse(cx - 21, cy - 12, 8, 8)
            painter.drawEllipse(cx + 13, cy - 12, 8, 8)
            painter.drawArc(cx - 14, cy + 16, 28, 16, 0, 180 * 16)
        elif self._mood == "greedy":
            painter.setBrush(QBrush(gold))
            painter.drawEllipse(cx - 23, cy - 14, 11, 11)
            painter.drawEllipse(cx + 12, cy - 14, 11, 11)
            painter.setBrush(QBrush(ink))
            painter.drawEllipse(cx - 20, cy - 11, 4, 4)
            painter.drawEllipse(cx + 15, cy - 11, 4, 4)
            painter.drawArc(cx - 16, cy + 5, 32, 20, 180 * 16, 180 * 16)
        elif self._mood == "thinking":
            painter.drawLine(cx - 24, cy - 12, cx - 12, cy - 10)
            painter.drawLine(cx + 12, cy - 10, cx + 24, cy - 12)
            painter.drawEllipse(cx - 19, cy - 8, 6, 6)
            painter.drawEllipse(cx + 13, cy - 8, 6, 6)
            painter.drawLine(cx - 10, cy + 14, cx + 10, cy + 14)
        else:
            blink = self._frame in (0, 1)
            if blink:
                painter.drawLine(cx - 23, cy - 10, cx - 13, cy - 10)
                painter.drawLine(cx + 13, cy - 10, cx + 23, cy - 10)
            else:
                painter.drawEllipse(cx - 22, cy - 14, 8, 8)
                painter.drawEllipse(cx + 14, cy - 14, 8, 8)
            painter.drawArc(cx - 14, cy + 4, 28, 18, 180 * 16, 180 * 16)

        painter.setBrush(QBrush(QColor("#202818")))
        painter.setPen(QPen(ink, 2))
        painter.drawRoundedRect(cx - 28, cy + 30, 56, 46, 12, 12)

        coin_y = cy + 44
        if self._mood in ("happy", "greedy"):
            coin_y -= 2 if self._frame % 8 < 4 else 0

        painter.setBrush(QBrush(gold))
        painter.setPen(QPen(QColor("#a8733a"), 2))
        painter.drawEllipse(cx + 18, coin_y, 22, 22)
        painter.end()

    def _paint_sprite(self, painter: QPainter) -> None:
        frames = {
            "idle": (0, 1),
            "happy": (1, 2),
            "greedy": (2, 1),
            "worried": (3,),
            "thinking": (3, 0),
        }
        frame_choices = frames.get(self._mood, frames["idle"])
        frame_index = frame_choices[(self._frame // 6) % len(frame_choices)]
        source_width = self._sprite_sheet.width() // 2
        source_height = self._sprite_sheet.height() // 2
        source = QRect(
            (frame_index % 2) * source_width,
            (frame_index // 2) * source_height,
            source_width,
            source_height,
        )
        bob = 3 if self._frame % 12 < 6 else 0
        target = QRect(8, 4 + bob, self.width() - 16, self.height() - 12)
        painter.drawPixmap(target, self._sprite_sheet, source)

    @staticmethod
    def _load_sprite_sheet() -> QPixmap:
        try:
            resource = files("gaingoblin").joinpath("assets/gain_goblin_sprite_sheet.png")
            with as_file(resource) as path:
                return QPixmap(str(path))
        except (FileNotFoundError, ModuleNotFoundError):
            return QPixmap()


class GoblinCompanionWidget(QWidget):
    NORMAL_WIDTH = 252
    COMPACT_WIDTH = 188
    NORMAL_GOBLIN_SIZE = 224
    COMPACT_GOBLIN_SIZE = 176

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.setObjectName("GoblinCompanionWidget")
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Maximum)
        self._compact = False

        self._speech = SpeechBubble(self)
        self._speech.setMaximumWidth(self.NORMAL_WIDTH)
        self._canvas = GoblinCanvas(self, self.NORMAL_GOBLIN_SIZE)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        layout.addWidget(self._speech)
        layout.addWidget(self._canvas, alignment=Qt.AlignmentFlag.AlignHCenter)

        self.setFixedWidth(self.NORMAL_WIDTH)

        self._timer = QTimer(self)
        self._timer.setInterval(180)
        self._timer.timeout.connect(self._canvas.step)
        self._timer.start()

    def set_compact(self, compact: bool) -> None:
        if self._compact == compact:
            return

        self._compact = compact
        self._speech.setVisible(not compact)
        self._canvas.set_display_size(
            self.COMPACT_GOBLIN_SIZE if compact else self.NORMAL_GOBLIN_SIZE
        )
        self.setFixedWidth(self.COMPACT_WIDTH if compact else self.NORMAL_WIDTH)
        self.updateGeometry()

    def sizeHint(self) -> QSize:
        return QSize(self.width(), 190 if self._compact else 292)

    def set_mood(self, mood: str) -> None:
        self._canvas.set_mood(mood)

    def set_speech(self, text: str) -> None:
        self._speech.set_text(text)
