from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from gaingoblin.calculations import to_decimal
from gaingoblin.models import Holding
from gaingoblin.widgets.dialog_utils import center_and_clamp_dialog


class HoldingDialog(QDialog):
    def __init__(self, holding: Holding | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._holding_id = holding.id if holding else None
        self.setWindowTitle("Edit Treasure Entry" if holding else "Add Treasure to the Hoard")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.resize(520, 560)
        self.setMinimumSize(420, 420)

        self.symbol_name = QLineEdit()
        self.shares = MoneyEdit(6)
        self.buy_price = MoneyEdit(4)
        self.buy_fees = MoneyEdit(4)
        self.target_sell_price = MoneyEdit(4)
        self.sell_fees = MoneyEdit(4)
        self.notes = QTextEdit()
        self.notes.setMinimumHeight(140)
        helper = QLabel("Goblin wants an exit number. You can change it later.")
        helper.setObjectName("HelperText")
        helper.setWordWrap(True)

        form_host = QWidget()
        form = QFormLayout(form_host)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.addRow("Symbol / Name", self.symbol_name)
        form.addRow("Shares", self.shares)
        form.addRow("Buy Price", self.buy_price)
        form.addRow("Buy Fees", self.buy_fees)
        form.addRow("Target Sell Price", self.target_sell_price)
        form.addRow("", helper)
        form.addRow("Sell Fees", self.sell_fees)
        form.addRow("Notes", self.notes)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(form_host)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(self.buttons)

        if holding:
            self._populate(holding)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_and_clamp_dialog(self, self.parentWidget())

    def accept(self) -> None:
        if not self.symbol_name.text().strip():
            QMessageBox.warning(self, "Missing Symbol / Name", "Enter a symbol or name before saving.")
            return
        try:
            self.holding()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Number", str(exc))
            return
        super().accept()

    def holding(self) -> Holding:
        return Holding(
            id=self._holding_id,
            symbol_name=self.symbol_name.text().strip(),
            shares=to_decimal(self.shares.text()),
            buy_price=to_decimal(self.buy_price.text()),
            buy_fees=to_decimal(self.buy_fees.text()),
            target_sell_price=to_decimal(self.target_sell_price.text()),
            sell_fees=to_decimal(self.sell_fees.text()),
            notes=self.notes.toPlainText().strip(),
        )

    def _populate(self, holding: Holding) -> None:
        self.symbol_name.setText(holding.symbol_name)
        self.shares.setText(str(holding.shares))
        self.buy_price.setText(str(holding.buy_price))
        self.buy_fees.setText(str(holding.buy_fees))
        self.target_sell_price.setText(str(holding.target_sell_price))
        self.sell_fees.setText(str(holding.sell_fees))
        self.notes.setPlainText(holding.notes)

class MoneyEdit(QLineEdit):
    def __init__(self, decimals: int, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._decimals = decimals
        self.setPlaceholderText("0")
        self.setText("0")

    def focusOutEvent(self, event) -> None:
        text = self.text().strip()
        try:
            value = to_decimal(text)
            quant = Decimal("1").scaleb(-self._decimals)
            self.setText(str(value.quantize(quant)))
        except ValueError:
            pass
        super().focusOutEvent(event)
