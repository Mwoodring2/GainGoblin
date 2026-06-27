from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import QFrame, QGridLayout, QLabel, QVBoxLayout, QWidget

from gaingoblin.theme import money_class_for_value


class SummaryCards(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._value_labels: dict[str, QLabel] = {}
        self._cards: list[QFrame] = []
        self._columns = 0

        self._layout = QGridLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setHorizontalSpacing(12)
        self._layout.setVerticalSpacing(10)

        for key, title, subtitle in (
            ("total_cost_basis", "Total Cost Basis", "coins spent"),
            ("target_net_value", "Target Net Value", "planned vault value"),
            ("projected_profit", "Projected Profit", "shiny difference"),
            ("roi_percent", "Portfolio ROI %", "goblin greed ratio"),
        ):
            card = QFrame()
            card.setObjectName("HeroProfitCard" if key == "projected_profit" else "SummaryCard")
            card.setMinimumHeight(92)

            title_label = QLabel(title)
            title_label.setObjectName("CardTitle")

            value_label = QLabel("$0.00")
            value_label.setObjectName("CardValue")

            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("CardSubtitle")

            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(14, 10, 14, 10)
            card_layout.setSpacing(3)
            card_layout.addWidget(title_label)
            card_layout.addWidget(value_label)
            card_layout.addWidget(subtitle_label)

            self._value_labels[key] = value_label
            self._cards.append(card)

        self._reflow(force=True)
        self.update_summary(
            {
                "total_cost_basis": Decimal("0"),
                "target_net_value": Decimal("0"),
                "projected_profit": Decimal("0"),
                "roi_percent": Decimal("0"),
            }
        )

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()

    def update_summary(self, summary: dict[str, Decimal]) -> None:
        values: dict[str, tuple[Decimal, str]] = {
            "total_cost_basis": (
                summary["total_cost_basis"],
                self._format_money(summary["total_cost_basis"]),
            ),
            "target_net_value": (
                summary["target_net_value"],
                self._format_money(summary["target_net_value"]),
            ),
            "projected_profit": (
                summary["projected_profit"],
                self._format_money(summary["projected_profit"]),
            ),
            "roi_percent": (summary["roi_percent"], f"{summary['roi_percent']}%"),
        }
        for key, (raw_value, display_value) in values.items():
            value_label = self._value_labels[key]
            value_label.setText(display_value)
            value_label.setObjectName(money_class_for_value(raw_value))
            value_label.style().unpolish(value_label)
            value_label.style().polish(value_label)

    def _reflow(self, force: bool = False) -> None:
        width = self.width()
        columns = 4 if width == 0 or width >= 860 else 2
        if not force and columns == self._columns:
            return

        self._columns = columns
        for card in self._cards:
            self._layout.removeWidget(card)
        for index, card in enumerate(self._cards):
            self._layout.addWidget(card, index // columns, index % columns)

    @staticmethod
    def _format_money(value: Decimal) -> str:
        return f"${value:,.2f}"
