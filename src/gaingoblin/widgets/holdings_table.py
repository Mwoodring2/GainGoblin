from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtGui import QBrush, QColor, QFont
from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QTableWidget, QTableWidgetItem

from gaingoblin.calculations import calculate_holding
from gaingoblin.goblin_personality import goblin_note_for_roi
from gaingoblin.models import Holding
from gaingoblin.theme import GOBLIN_COLORS


class HoldingsTable(QTableWidget):
    HEADERS = [
        "Account",
        "Symbol",
        "Shares",
        "Buy Price",
        "Buy Fees",
        "Target Sell",
        "Sell Fees",
        "Cost Basis",
        "Target Net",
        "Projected Profit",
        "ROI %",
        "Goblin Note",
        "Notes",
    ]
    TOOL_TIPS = {
        "Cost Basis": "shares x buy price + buy fees",
        "Target Net": "shares x target sell price - sell fees",
        "Projected Profit": "target net value - cost basis",
        "ROI %": "projected profit / cost basis",
        "Goblin Note": "mood based on planned return",
    }
    COLUMN_WIDTHS = {
        "Account": 130,
        "Symbol": 90,
        "Shares": 120,
        "Buy Price": 115,
        "Buy Fees": 105,
        "Target Sell": 120,
        "Sell Fees": 105,
        "Cost Basis": 125,
        "Target Net": 125,
        "Projected Profit": 145,
        "ROI %": 90,
        "Goblin Note": 190,
        "Notes": 220,
    }

    def __init__(self, parent=None) -> None:
        super().__init__(0, len(self.HEADERS), parent)
        self._holdings: list[Holding] = []
        self.setObjectName("HoldingsLedger")
        self.setHorizontalHeaderLabels(self.HEADERS)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.verticalHeader().setVisible(False)
        self.verticalHeader().setDefaultSectionSize(34)
        self.setSortingEnabled(True)
        header = self.horizontalHeader()
        header.setMinimumSectionSize(80)
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header.setStretchLastSection(True)
        self._apply_column_widths()
        for column, title in enumerate(self.HEADERS):
            item = self.horizontalHeaderItem(column)
            if item is not None and title in self.TOOL_TIPS:
                item.setToolTip(self.TOOL_TIPS[title])

    def set_holdings(self, holdings: list[Holding]) -> None:
        self.setSortingEnabled(False)
        self._holdings = holdings
        self.setRowCount(len(holdings))
        for row, holding in enumerate(holdings):
            calculated = calculate_holding(holding)
            goblin_note = goblin_note_for_roi(calculated.roi_percent, calculated.projected_profit)
            if holding.target_sell_price <= Decimal("0"):
                goblin_note = "No exit plan? Risky treasure."
            values = [
                holding.account_name,
                holding.symbol_name,
                str(holding.shares),
                self._format_money(holding.buy_price),
                self._format_money(holding.buy_fees),
                self._format_money(holding.target_sell_price),
                self._format_money(holding.sell_fees),
                self._format_money(calculated.cost_basis),
                self._format_money(calculated.target_net_value),
                self._format_money(calculated.projected_profit),
                f"{calculated.roi_percent}%",
                goblin_note,
                holding.notes,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setData(Qt.ItemDataRole.UserRole, holding)
                if column in {2, 3, 4, 5, 6, 7, 8, 9, 10}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self._style_item(item, column, calculated.projected_profit, holding.target_sell_price)
                if self.HEADERS[column] in self.TOOL_TIPS:
                    item.setToolTip(self.TOOL_TIPS[self.HEADERS[column]])
                self.setItem(row, column, item)
        self._apply_column_widths()
        self.setSortingEnabled(True)

    def selected_holding(self) -> Holding | None:
        selected = self.selectionModel().selectedRows()
        if not selected:
            return None
        row = selected[0].row()
        item = self.item(row, 0)
        if item is None:
            return None
        holding = item.data(Qt.ItemDataRole.UserRole)
        return holding if isinstance(holding, Holding) else None

    def _apply_column_widths(self) -> None:
        for column, title in enumerate(self.HEADERS):
            width = self.COLUMN_WIDTHS.get(title)
            if width is not None:
                self.setColumnWidth(column, width)

    def _style_item(
        self,
        item: QTableWidgetItem,
        column: int,
        projected_profit: Decimal,
        target_sell_price: Decimal,
    ) -> None:
        if column in {9, 10}:
            font = QFont(item.font())
            font.setBold(True)
            item.setFont(font)
            color = GOBLIN_COLORS["danger"] if projected_profit < Decimal("0") else GOBLIN_COLORS["green"]
            item.setForeground(QBrush(QColor(color)))
        elif column == 11 and target_sell_price <= Decimal("0"):
            item.setForeground(QBrush(QColor(GOBLIN_COLORS["gold"])))
        elif column == 11 and projected_profit < Decimal("0"):
            item.setForeground(QBrush(QColor(GOBLIN_COLORS["danger"])))

    @staticmethod
    def _format_money(value: Decimal) -> str:
        return f"${value:,.2f}"
