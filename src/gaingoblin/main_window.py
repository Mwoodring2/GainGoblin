from __future__ import annotations

import csv
from decimal import Decimal
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from gaingoblin import __version__
from gaingoblin.calculations import calculate_holding, portfolio_summary
from gaingoblin.database import HoldingRepository
from gaingoblin.goblin_personality import (
    PortfolioPersonalityState,
    mood_for_state,
    speech_for_state,
)
from gaingoblin.models import Holding
from gaingoblin.ui.breakpoints import LayoutBreakpoint, breakpoint_for_size
from gaingoblin.ui.flow_layout import FlowLayout
from gaingoblin.ui.stage_geometry import StageGeometry
from gaingoblin.widgets.clipboard_shell import ClipboardShell
from gaingoblin.widgets.goblin_companion import GoblinCompanionWidget
from gaingoblin.widgets.holding_dialog import HoldingDialog
from gaingoblin.widgets.holdings_table import HoldingsTable
from gaingoblin.widgets.import_dialog import ImportDialog
from gaingoblin.widgets.range_calculator_dialog import RangeCalculatorDialog
from gaingoblin.widgets.summary_cards import SummaryCards


class MainWindow(QMainWindow):
    def __init__(self, repository: HoldingRepository) -> None:
        super().__init__()
        self.repository = repository
        self.holdings: list[Holding] = []
        self._loading_accounts = False
        self._breakpoint: LayoutBreakpoint | None = None
        self._previous_projected_profit: Decimal | None = None
        self._previous_missing_target_count: int | None = None
        self.setWindowTitle(f"Gain Goblin v{__version__}")
        self.resize(1240, 860)
        self.setMinimumSize(980, 700)

        self._workspace_content = QWidget()
        self._workspace_content.setObjectName("WorkspaceContent")

        self._title = QLabel("Gain Goblin", self._workspace_content)
        self._title.setObjectName("AppTitle")
        self._title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._subtitle = QLabel("Manual profit ledger", self._workspace_content)
        self._subtitle.setObjectName("AppSubtitle")
        self._subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.summary_cards = SummaryCards(self._workspace_content)
        self.table = HoldingsTable()

        self.account_filter = QComboBox()
        self.account_filter.currentIndexChanged.connect(self._account_filter_changed)

        self.add_button = QPushButton("Add Holding")
        self.import_button = QPushButton("Import File / Paste")
        self.range_button = QPushButton("Range Calculator")
        self.edit_button = QPushButton("Edit Selected")
        self.delete_button = QPushButton("Delete Selected")
        self.export_button = QPushButton("Export CSV")
        self._action_buttons = [
            self.add_button,
            self.import_button,
            self.range_button,
            self.edit_button,
            self.delete_button,
            self.export_button,
        ]
        self.add_button.setObjectName("PrimaryActionButton")
        self.import_button.setObjectName("SecondaryActionButton")
        self.range_button.setObjectName("SecondaryActionButton")
        self.export_button.setObjectName("SecondaryActionButton")
        self.edit_button.setObjectName("SecondaryActionButton")
        self.delete_button.setObjectName("DangerActionButton")
        self.import_button.setToolTip("Import local CSV, XLSX, PDF, or pasted holdings text.")
        self.range_button.setToolTip("Calculate possible gain/loss using manually entered average high and low prices.")
        self._base_button_widths = {
            self.add_button: 150,
            self.import_button: 180,
            self.range_button: 170,
            self.edit_button: 150,
            self.delete_button: 160,
            self.export_button: 144,
        }
        for button in self._action_buttons:
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

        self.add_button.clicked.connect(self.add_holding)
        self.import_button.clicked.connect(self.import_spreadsheet)
        self.range_button.clicked.connect(self.open_range_calculator)
        self.edit_button.clicked.connect(self.edit_selected)
        self.delete_button.clicked.connect(self.delete_selected)
        self.export_button.clicked.connect(self.export_csv)
        self.table.itemDoubleClicked.connect(lambda _item: self.edit_selected())
        self.table.itemSelectionChanged.connect(self._update_buttons)

        filter_row = QHBoxLayout()
        filter_row.setSpacing(8)
        filter_row.addWidget(QLabel("Account"))
        filter_row.addWidget(self.account_filter, 1)

        self._actions = FlowLayout(horizontal_spacing=8, vertical_spacing=8)
        for button in self._action_buttons:
            self._actions.addWidget(button)

        self._ledger_panel = QFrame(self._workspace_content)
        self._ledger_panel.setObjectName("LedgerPanel")
        self._ledger_layout = QVBoxLayout(self._ledger_panel)
        self._ledger_layout.setContentsMargins(18, 16, 18, 18)
        self._ledger_layout.setSpacing(12)
        self._ledger_layout.addLayout(filter_row)
        self._ledger_layout.addLayout(self._actions)
        self._ledger_layout.addWidget(self.table, 1)

        self._companion_panel = QFrame(self._workspace_content)
        self._companion_panel.setObjectName("CompanionPanel")
        companion_layout = QVBoxLayout(self._companion_panel)
        companion_layout.setContentsMargins(8, 8, 8, 10)
        self._goblin_companion = GoblinCompanionWidget(self._companion_panel)
        companion_layout.addWidget(
            self._goblin_companion,
            1,
            alignment=Qt.AlignmentFlag.AlignHCenter,
        )

        host = ClipboardShell()
        host.set_content_widget(self._workspace_content)
        self._clipboard_shell = host
        self.setCentralWidget(host)

        self.refresh()
        self._apply_stage_layout()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._apply_stage_layout()

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
            self._goblin_companion.play_event("holding_added")

    def import_spreadsheet(self) -> None:
        dialog = ImportDialog(self.repository, parent=self)
        if dialog.exec():
            result = dialog.import_result
            if result is not None:
                self.refresh(
                    f"Imported {result.imported_count} holdings. Skipped {result.skipped_count}."
                )
                import_event = (
                    "import_failed"
                    if result.imported_count == 0 or result.skipped_count > result.imported_count
                    else "import_success"
                )
                self._goblin_companion.play_event(import_event)
            else:
                self.refresh()

    def open_range_calculator(self) -> None:
        selected = self.table.selected_holding()
        self._goblin_companion.play_event("thinking_tap")
        dialog = RangeCalculatorDialog(selected_holding=selected, parent=self)
        dialog.calculation_succeeded.connect(lambda: self._goblin_companion.play_event("greedy_coin_jiggle"))
        dialog.validation_failed.connect(lambda: self._goblin_companion.play_event("worried_sweat"))
        dialog.fetch_started.connect(lambda: self._goblin_companion.play_event("thinking_tap"))
        dialog.fetch_succeeded.connect(lambda: self._goblin_companion.play_event("greedy_coin_jiggle"))
        dialog.fetch_failed.connect(lambda: self._goblin_companion.play_event("worried_sweat"))
        dialog.exec()

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
            self._goblin_companion.play_event("delete")

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

    def _apply_stage_layout(self) -> None:
        if not hasattr(self, "_clipboard_shell"):
            return

        geometry = self._clipboard_shell.stage_geometry()
        self._workspace_content.setGeometry(geometry.content_rect)
        self._update_responsive_layout(geometry)

        origin = geometry.content_rect.topLeft()

        def relative(rect: QRect) -> QRect:
            return QRect(rect).translated(-origin)

        title_rect = relative(geometry.title_rect)
        title_height = max(26, round(title_rect.height() * 0.6))
        self._title.setGeometry(
            title_rect.x(),
            title_rect.y(),
            title_rect.width(),
            title_height,
        )
        self._subtitle.setGeometry(
            title_rect.x(),
            title_rect.y() + title_height - 2,
            title_rect.width(),
            max(16, title_rect.height() - title_height + 2),
        )
        self.summary_cards.setGeometry(relative(geometry.summary_rect))
        self._ledger_panel.setGeometry(relative(geometry.ledger_rect))
        self._companion_panel.setGeometry(relative(geometry.companion_rect))

    def _update_responsive_layout(self, geometry: StageGeometry | None = None) -> None:
        if not hasattr(self, "_goblin_companion"):
            return

        if geometry is None:
            geometry = self._clipboard_shell.stage_geometry()
        breakpoint = breakpoint_for_size(
            geometry.stage_rect.width(),
            geometry.stage_rect.height(),
        )
        if breakpoint == self._breakpoint:
            return

        self._breakpoint = breakpoint
        margin = breakpoint.content_margin
        self._ledger_layout.setContentsMargins(margin, margin, margin, margin)
        self._ledger_layout.setSpacing(8 if breakpoint.compact else 12)
        self._actions.set_spacing(6 if breakpoint.compact else 8, 6 if breakpoint.compact else 8)
        for button in self._action_buttons:
            button.setMinimumWidth(
                max(self._base_button_widths[button], breakpoint.action_button_min_width)
            )

        self.summary_cards.set_breakpoint(breakpoint)
        self._goblin_companion.set_breakpoint(breakpoint)

    def _position_goblin_companion(self) -> None:
        self._apply_stage_layout()

    def _update_goblin_companion(self) -> None:
        if not hasattr(self, "_goblin_companion"):
            return

        summary = self._calculate_portfolio_summary_for_goblin()
        missing_target_count = int(summary["missing_target_count"])
        projected_profit = summary["projected_profit"]
        state = PortfolioPersonalityState(
            total_cost_basis=summary["total_cost_basis"],
            target_net_value=summary["target_net_value"],
            projected_profit=projected_profit,
            roi_percent=summary["roi_percent"],
            missing_target_count=missing_target_count,
        )

        self._goblin_companion.set_mood(mood_for_state(state))
        self._goblin_companion.set_speech(speech_for_state(state))
        self._play_summary_transition_if_needed(projected_profit, missing_target_count)

    def _play_summary_transition_if_needed(
        self, projected_profit: Decimal, missing_target_count: int
    ) -> None:
        previous_profit = self._previous_projected_profit
        previous_missing = self._previous_missing_target_count
        self._previous_projected_profit = projected_profit
        self._previous_missing_target_count = missing_target_count

        if previous_profit is None or previous_missing is None:
            return
        if previous_profit <= Decimal("0") < projected_profit:
            self._goblin_companion.play_event("profit_up")
        elif previous_profit >= Decimal("0") > projected_profit:
            self._goblin_companion.play_event("profit_down")
        elif previous_missing == 0 and missing_target_count > 0:
            self._goblin_companion.play_event("thinking_tap")

    def _calculate_portfolio_summary_for_goblin(self) -> dict[str, Decimal | int]:
        summary: dict[str, Decimal | int] = dict(portfolio_summary(self.holdings))
        summary["missing_target_count"] = sum(
            1 for holding in self.holdings if holding.target_sell_price <= Decimal("0")
        )
        return summary
