from __future__ import annotations

from decimal import Decimal
from importlib.resources import files

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


def _asset_url(relative_path: str) -> str:
    try:
        path = files("gaingoblin").joinpath(relative_path)
        return str(path).replace("\\", "/")
    except (FileNotFoundError, ModuleNotFoundError):
        return ""


def _qss_url(relative_path: str) -> str:
    path = _asset_url(relative_path)
    return f'url("{path}")' if path else "none"


def build_goblin_qss() -> str:
    c = GOBLIN_COLORS
    center_panel = _qss_url("assets/clipboard_kit/center_panel.png")
    summary_panel = _qss_url("assets/clipboard_kit/summary_panel.png")
    table_panel = _qss_url("assets/clipboard_kit/table_panel.png")
    primary_button = _qss_url("assets/clipboard_kit/primary_button.png")
    secondary_button = _qss_url("assets/clipboard_kit/secondary_button_left.png")
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
        color: #9fca39;
        font-size: 32px;
        font-weight: 800;
    }}

    QLabel#AppSubtitle {{
        color: {c["ink"]};
        font-size: 13px;
        font-weight: 700;
    }}

    QLabel#HelperText,
    QLabel#CardSubtitle {{
        color: #8f815f;
        font-size: 12px;
    }}

    QFrame#SummaryCard {{
        border-image: {center_panel} 18 18 18 18 stretch stretch;
        border-width: 18px;
        color: {c["ink"]};
    }}

    QFrame#HeroProfitCard {{
        border-image: {summary_panel} 18 18 18 18 stretch stretch;
        border-width: 18px;
        color: {c["ink"]};
    }}

    QLabel#CardTitle {{
        color: {c["ink"]};
        font-size: 12px;
        font-weight: 600;
    }}

    QLabel#CardValue,
    QLabel#PositiveMoney,
    QLabel#NegativeMoney {{
        font-size: 22px;
        font-weight: 700;
    }}

    QLabel#PositiveMoney {{
        color: #36570f;
    }}

    QLabel#NegativeMoney {{
        color: #8f2f25;
    }}

    QFrame#LedgerPanel {{
        border-image: {table_panel} 22 22 22 22 stretch stretch;
        border-width: 22px;
    }}

    QFrame#CompanionPanel {{
        background-color: rgba(30, 25, 17, 40);
        border: 0;
    }}

    QPushButton {{
        background-color: {c["green_dark"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 10px;
        padding: 8px 12px;
        font-weight: 700;
    }}

    QPushButton#PrimaryActionButton {{
        border-image: {primary_button} 12 18 12 18 stretch stretch;
        border-width: 12px 18px;
        color: #f8f0d1;
        min-height: 22px;
    }}

    QPushButton#SecondaryActionButton {{
        border-image: {secondary_button} 12 18 12 18 stretch stretch;
        border-width: 12px 18px;
        color: #f3ead2;
        min-height: 22px;
    }}

    QPushButton#DangerActionButton {{
        background-color: #5c2d26;
        border-color: #9f5d45;
    }}

    QPushButton:hover {{
        background-color: {c["green"]};
        color: #10140d;
    }}

    QPushButton:pressed {{
        background-color: {c["bronze"]};
    }}

    QPushButton:disabled {{
        background-color: {c["panel"]};
        color: {c["muted"]};
    }}

    QTableView,
    QTableWidget {{
        background-color: rgba(25, 24, 20, 225);
        alternate-background-color: rgba(40, 36, 28, 225);
        color: {c["text"]};
        gridline-color: {c["border"]};
        border: 1px solid #5f4a2a;
        border-radius: 8px;
        selection-background-color: {c["green_dark"]};
        selection-color: {c["text"]};
    }}

    QHeaderView::section {{
        background-color: #2b2116;
        color: {c["gold"]};
        border: 0px;
        border-right: 1px solid #5f4a2a;
        padding: 8px;
        font-weight: 700;
    }}

    QLineEdit,
    QDoubleSpinBox,
    QSpinBox,
    QTextEdit {{
        background-color: {c["panel"]};
        color: {c["text"]};
        border: 1px solid {c["border"]};
        border-radius: 8px;
        padding: 6px;
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
