from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QApplication

GOBLIN_COLORS = {
    "bg": "#11140f",
    "panel": "#1a2117",
    "panel_alt": "#202818",
    "card": "#202818",
    "card_hover": "#27311d",
    "border": "#3a4a2e",
    "text": "#f3ead2",
    "muted": "#b7aa8a",
    "green": "#8ccf5f",
    "green_dark": "#4f7f34",
    "gold": "#e0b84f",
    "bronze": "#a8733a",
    "danger": "#d66a5c",
    "danger_bg": "#3a1f1d",
    "paper": "#d9bd89",
    "paper_dark": "#b78d56",
    "ink": "#21170f",
    "wood": "#3b2110",
}


def money_class_for_value(value: Decimal) -> str:
    if value < Decimal("0"):
        return "NegativeMoney"
    return "PositiveMoney"


def build_goblin_qss() -> str:
    c = GOBLIN_COLORS
    return f"""
    QMainWindow {{
        background-color: {c["bg"]};
        color: {c["text"]};
    }}

    QDialog {{
        background-color: {c["bg"]};
        color: {c["text"]};
    }}

    QWidget {{
        color: {c["text"]};
        font-family: "Segoe UI", Arial, sans-serif;
        font-size: 13px;
    }}

    QWidget#ClipboardShell,
    QWidget#WorkspaceContent {{
        background-color: transparent;
    }}

    QLabel#AppTitle {{
        color: #a6d942;
        font-size: 30px;
        font-weight: 850;
        padding: 0 8px;
    }}

    QLabel#AppSubtitle {{
        color: {c["ink"]};
        font-size: 13px;
        font-weight: 750;
    }}

    QLabel#HelperText {{
        color: #c9b987;
        font-size: 12px;
    }}

    QLabel#CardSubtitle {{
        color: #75623e;
        font-size: 12px;
    }}

    QFrame#SummaryCard {{
        background-color: rgba(232, 202, 150, 240);
        border: 1px solid rgba(105, 78, 38, 220);
        border-radius: 16px;
        color: {c["ink"]};
    }}

    QFrame#HeroProfitCard {{
        background-color: rgba(238, 207, 139, 245);
        border: 2px solid rgba(147, 110, 39, 235);
        border-radius: 16px;
        color: {c["ink"]};
    }}

    QLabel#CardTitle {{
        color: {c["ink"]};
        font-size: 12px;
        font-weight: 750;
    }}

    QLabel#CardValue,
    QLabel#PositiveMoney,
    QLabel#NegativeMoney {{
        font-size: 22px;
        font-weight: 850;
    }}

    QLabel#PositiveMoney {{
        color: #31560f;
    }}

    QLabel#NegativeMoney {{
        color: #8f2f25;
    }}

    QFrame#LedgerPanel {{
        background-color: rgba(30, 24, 17, 235);
        border: 1px solid #806338;
        border-radius: 18px;
    }}

    QFrame#CompanionPanel {{
        background-color: rgba(222, 190, 132, 230);
        border: 1px solid #806338;
        border-radius: 16px;
    }}

    QFrame#RangeResultsPanel {{
        background-color: rgba(32, 40, 24, 220);
        border: 1px solid #806338;
        border-radius: 12px;
        padding: 8px;
    }}

    QPushButton {{
        background-color: {c["green_dark"]};
        color: {c["text"]};
        border: 1px solid #6f8c3a;
        border-radius: 8px;
        padding: 8px 12px;
        font-weight: 750;
    }}

    QPushButton#PrimaryActionButton {{
        background-color: #6c7f16;
        color: #fff4c8;
        border-color: #d3b64c;
    }}

    QPushButton#SecondaryActionButton {{
        background-color: #2a241b;
        color: #f3ead2;
        border-color: #8d713b;
    }}

    QPushButton#DangerActionButton {{
        background-color: #6b3329;
        border-color: #b0664c;
        color: #ffe6d8;
    }}

    QPushButton:hover {{
        background-color: {c["green"]};
        color: #10140d;
    }}

    QPushButton:pressed {{
        background-color: {c["bronze"]};
    }}

    QPushButton:disabled {{
        background-color: #211d17;
        color: #8d8065;
        border-color: #4f4432;
    }}

    QTableView,
    QTableWidget {{
        background-color: #1b1a14;
        alternate-background-color: #202519;
        color: #f7efd7;
        gridline-color: #40572e;
        border: 1px solid #6c542f;
        border-radius: 8px;
        selection-background-color: {c["green_dark"]};
        selection-color: {c["text"]};
    }}

    QTableWidget#ImportPreviewTable {{
        background-color: #191812;
        alternate-background-color: #211f18;
        gridline-color: #4c3d28;
    }}

    QHeaderView::section {{
        background-color: #2b2116;
        color: {c["gold"]};
        border: 0px;
        border-right: 1px solid #5f4a2a;
        padding: 8px;
        font-weight: 800;
    }}

    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QComboBox,
    QTextEdit {{
        background-color: #1b2118;
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 6px;
        selection-background-color: {c["green_dark"]};
    }}

    QComboBox::drop-down {{
        border: 0;
        width: 22px;
    }}

    QComboBox QAbstractItemView {{
        background-color: {c["panel_alt"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        selection-background-color: {c["green_dark"]};
    }}

    QScrollArea {{
        border: 0;
        background-color: transparent;
    }}

    QStatusBar {{
        background-color: {c["panel"]};
        color: {c["muted"]};
        border-top: 1px solid {c["border"]};
    }}

    QToolTip {{
        background-color: {c["panel_alt"]};
        color: {c["text"]};
        border: 1px solid {c["gold"]};
        padding: 6px;
    }}
    """


def apply_goblin_theme(app: QApplication) -> None:
    app.setStyleSheet(build_goblin_qss())


def apply_dark_theme(app: QApplication) -> None:
    apply_goblin_theme(app)
