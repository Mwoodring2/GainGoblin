from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from gaingoblin import __version__
from gaingoblin.calculations import calculate_holding, portfolio_summary
from gaingoblin.database import HoldingRepository
from gaingoblin.goblin_personality import PortfolioPersonalityState, mood_for_state, speech_for_state
from gaingoblin.models import Holding
from gaingoblin.widgets.clipboard_shell import ClipboardShell
from gaingoblin.widgets.goblin_companion import GoblinCompanionWidget
from gaingoblin.widgets.holding_dialog import HoldingDialog
from gaingoblin.widgets.holdings_table import HoldingsTable
from gaingoblin.widgets.import_dialog import ImportDialog
from gaingoblin.widgets.summary_cards import SummaryCards


class MainWindow(QMainWindow):
    def __init__(self, repository: HoldingRepository) -> None:
        super().__init__()
        self.repository = repository
        self.holdings: list[Holding] = []
        self._loading_accounts = False
        self.setWindowTitle(f"Gain Goblin v{__version__}")
        self.resize(1240, 860)
        self.setMinimumSize(980, 700)

        title = QLabel("Gain Goblin")
        title.setObjectName("AppTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        subtitle = QLabel("Manual profit ledger")
        subtitle.setObjectName("AppSubtitle")
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.summary_cards = SummaryCards()
        self.table = HoldingsTable()
        self.table.setObjectName("HoldingsLedger")

        self.account_filter = QComboBox()
        self.account_filter.currentIndexChanged.connect(self._account_filter_changed)

        self.add_button = QPushButton("Add Holding")
        self.import_button = QPushButton("Import Spreadsheet")
        self.edit_button = QPushButton("Edit Selected")
        self.delete_button = QPushButton("Delete Selected")
        self.export_button = QPushButton("Export CSV")
        self.add_button.setObjectName("PrimaryActionButton")
        self.import_button.setObjectName("SecondaryActionButton")
        self.export_button.setObjectName("SecondaryActionButton")
        self.edit_button.setObjectName("SecondaryActionButton")
        self.delete_button.setObjectName("DangerActionButton")
        self.import_button.setToolTip("Import holdings from a CSV or XLSX file.")

        self.add_button.clicked.connect(self.add_holding)
        self.import_button.clicked.connect(self.import_spreadsheet)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        self.export_button.clicked.connect(self.export_csv)
        self.table.itemDoubleClicked.connect(lambda _item: self.edit_selected())
        self.table.itemSelectionChanged.connect(self._update_buttons)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Account"))
        filter_row.addWidget(self.account_filter, 1)

        actions = QHBoxLayout()
        actions.setSpacing(10)
        actions.addWidget(self.add_button)
        actions.addWidget(self.import_button)
        actions.addWidget(self.edit_button)
        actions.addWidget(self.delete_button)
        actions.addStretch(1)
        actions.addWidget(self.export_button)

        ledger_panel = QFrame()
        ledger_panel.setObjectName("LedgerPanel")
        ledger_layout = QVBoxLayout(ledger_panel)
        ledger_layout.setContentsMargins(16, 14, 16, 16)
        ledger_layout.setSpacing(12)
        ledger_layout.addLayout(filter_row)
        ledger_layout.addLayout(actions)
        ledger_layout.addWidget(self.table, 1)

        self._companion_panel = QFrame()
        self._companion_panel.setObjectName("CompanionPanel")
        self._companion_panel.setMinimumWidth(178)
        self._companion_panel.setMaximumWidth(268)
        companion_layout = QVBoxLayout(self._companion_panel)
        companion_layout.setContentsMargins(6, 10, 6, 10)
        companion_layout.addStretch(1)
        self._goblin_companion = GoblinCompanionWidget(self._companion_panel)
        companion_layout.addWidget(
            self._goblin_companion,
            alignment=Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignBottom,
        )

        workspace_row = QHBoxLayout()
        workspace_row.setSpacing(12)
        workspace_row.addWidget(ledger_panel, 1)
        workspace_row.addWidget(self._companion_panel, 0)

        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(10)
        content_layout.addWidget(title)
        content_layout.addWidget(subtitle)
        content_layout.addWidget(self.summary_cards)
        content_layout.addLayout(workspace_row, 1)

        self._workspace_content = QWidget()
        self._workspace_content.setObjectName("WorkspaceContent")
        self._workspace_content.setLayout(content_layout)

        host = ClipboardShell()
        host.set_content_widget(self._workspace_content)
        self._clipboard_shell = host
        self.setCentralWidget(host)

        self.refresh()
        self._update_responsive_layout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_responsive_layout()

    def refresh(self, status_message: str | None = None) -> None:
        selected_account_id = self._selected_account_id()
        self._refresh_account_filter(selected_account_id)
        selected_account_id = self._selected_account_id()
        self.holdings = self.repository.list_holdings(selected_account_id)
        self.table.set_holdings(self.holdings)
        self.summary_cards.update_summary(portfolio_summary(self.holdings))
        self._update_buttons()
        self._update_goblin_companion()
        if status_message:
            self.statusBar().showMessage(status_message, 4000)

    def add_holding(self) -> None:
        dialog = HoldingDialog(parent=self)
        account_id = self._selected_account_id()
        if account_id is not None:
            account_name = self.account_filter.currentText()
            dialog.set_account(account_id, account_name)
        if dialog.exec():
            self.repository.add_holding(dialog.holding())
            self.refresh("Holding added to the hoard.")

    def import_spreadsheet(self) -> None:
        dialog = ImportDialog(self.repository, parent=self)
        if dialog.exec():
            result = dialog.import_result
            if result is not None:
                self.refresh(
                    f"Imported {result.imported_count} holdings. Skipped {result.skipped_count}."
                )
            else:
                self.refresh()

    def edit_selected(self) -> None:
        holding = self.table.selected_holding()
        if holding is None:
            return

        dialog = HoldingDialog(holding=holding, parent=self)
        if dialog.exec():
            self.repository.update_holding(dialog.holding())
            self.refresh("Treasure ledger updated.")

    def delete_selected(self) -> None:
        holding = self.table.selected_holding()
        if holding is None or holding.id is None:
            return

        answer = QMessageBox.question(
            self,
            "Delete Holding",
            f"Delete {holding.symbol_name}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.repository.delete_holding(holding.id)
            self.refresh("Treasure removed from the hoard.")

    def export_csv(self) -> None:
        path, _selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export CSV",
            str(Path.home() / "gaingoblin_holdings.csv"),
            "CSV Files (*.csv)",
        )
        if not path:
            return

        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "account_name",
                    "symbol_name",
                    "shares",
                    "buy_price",
                    "buy_fees",
                    "target_sell_price",
                    "sell_fees",
                    "cost_basis",
                    "target_gross_value",
                    "target_net_value",
                    "projected_profit",
                    "roi_percent",
                    "goblin_note",
                    "notes",
                ]
            )
            for holding in self.holdings:
                calculated = calculate_holding(holding)
                writer.writerow(
                    [
                        holding.account_name,
                        holding.symbol_name,
                        holding.shares,
                        holding.buy_price,
                        holding.buy_fees,
                        holding.target_sell_price,
                        holding.sell_fees,
                        calculated.cost_basis,
                        calculated.target_gross_value,
                        calculated.target_net_value,
                        calculated.projected_profit,
                        calculated.roi_percent,
                        calculated.goblin_note,
                        holding.notes,
                    ]
                )

        QMessageBox.information(self, "Export Complete", f"CSV exported to:\n{path}")
        self.statusBar().showMessage("Export complete. Ledger packed.", 4000)

    def _refresh_account_filter(self, selected_account_id: int | None) -> None:
        self._loading_accounts = True
        self.account_filter.clear()
        self.account_filter.addItem("All Accounts", None)
        selected_index = 0
        for account in self.repository.list_accounts():
            self.account_filter.addItem(account.name, account.id)
            if selected_account_id is not None and account.id == selected_account_id:
                selected_index = self.account_filter.count() - 1
        self.account_filter.setCurrentIndex(selected_index)
        self._loading_accounts = False

    def _selected_account_id(self) -> int | None:
        value = self.account_filter.currentData()
        return int(value) if value is not None else None

    def _account_filter_changed(self) -> None:
        if not self._loading_accounts:
            self.refresh()

    def _update_buttons(self) -> None:
        has_selection = self.table.selected_holding() is not None
        self.edit_button.setEnabled(has_selection)
        self.delete_button.setEnabled(has_selection)
        self.export_button.setEnabled(bool(self.holdings))

    def _update_responsive_layout(self) -> None:
        if not hasattr(self, "_goblin_companion"):
            return

        art_width = self._clipboard_shell.art_rect().width() if hasattr(self, "_clipboard_shell") else self.width()
        compact = art_width < 1120 or self.height() < 760
        self._goblin_companion.set_compact(compact)
        self._companion_panel.setFixedWidth(192 if compact else 268)

    def _position_goblin_companion(self) -> None:
        self._update_responsive_layout()

    def _update_goblin_companion(self) -> None:
        if not hasattr(self, "_goblin_companion"):
            return

        summary = self._calculate_portfolio_summary_for_goblin()
        state = PortfolioPersonalityState(
            total_cost_basis=summary["total_cost_basis"],
            target_net_value=summary["target_net_value"],
            projected_profit=summary["projected_profit"],
            roi_percent=summary["roi_percent"],
            missing_target_count=int(summary["missing_target_count"]),
        )

        self._goblin_companion.set_mood(mood_for_state(state))
        self._goblin_companion.set_speech(speech_for_state(state))

    def _calculate_portfolio_summary_for_goblin(self) -> dict[str, Decimal | int]:
        summary: dict[str, Decimal | int] = dict(portfolio_summary(self.holdings))
        summary["missing_target_count"] = sum(
            1 for holding in self.holdings if holding.target_sell_price <= Decimal("0")
        )
        return summary
