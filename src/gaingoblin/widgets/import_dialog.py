from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from gaingoblin.database import DEFAULT_ACCOUNT_NAME, HoldingRepository
from gaingoblin.importers.holdings_importer import create_import_preview, import_preview_rows
from gaingoblin.importers.import_models import ImportPreviewRow, ImportResult, RawImportRow
from gaingoblin.importers.spreadsheet_reader import read_spreadsheet
from gaingoblin.widgets.dialog_utils import center_and_clamp_dialog


class ImportDialog(QDialog):
    HEADERS = [
        "Row",
        "Status",
        "Message",
        "Account",
        "Symbol",
        "Shares",
        "Buy Price",
        "Target Sell",
        "Notes",
    ]

    def __init__(self, repository: HoldingRepository, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.repository = repository
        self.preview_rows: list[ImportPreviewRow] = []
        self.raw_rows: list[RawImportRow] = []
        self.import_result: ImportResult | None = None
        self._source_path: Path | None = None

        self.setWindowTitle("Import Holdings Spreadsheet")
        self.setModal(True)
        self.setSizeGripEnabled(True)
        self.resize(860, 620)
        self.setMinimumSize(640, 460)

        intro = QLabel(
            "Import holdings from a local CSV or XLSX file. No brokerage login, sync, or live prices."
        )
        intro.setObjectName("HelperText")
        intro.setWordWrap(True)

        self.path_edit = QLineEdit()
        self.path_edit.setReadOnly(True)
        browse_button = QPushButton("Choose File")
        browse_button.clicked.connect(self.choose_file)

        path_row = QHBoxLayout()
        path_row.addWidget(self.path_edit, 1)
        path_row.addWidget(browse_button)

        self.account_combo = QComboBox()
        self.account_combo.setEditable(True)
        self._populate_accounts()
        self.account_combo.currentTextChanged.connect(self._rebuild_preview)

        account_row = QHBoxLayout()
        account_row.addWidget(QLabel("Default Account"))
        account_row.addWidget(self.account_combo, 1)

        self.summary_label = QLabel("Choose a CSV or XLSX file to preview.")
        self.summary_label.setObjectName("HelperText")
        self.summary_label.setWordWrap(True)

        self.preview_table = QTableWidget(0, len(self.HEADERS))
        self.preview_table.setHorizontalHeaderLabels(self.HEADERS)
        self.preview_table.setAlternatingRowColors(True)
        self.preview_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.preview_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.preview_table.verticalHeader().setVisible(False)
        self.preview_table.setMinimumHeight(320)

        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.addWidget(intro)
        content_layout.addLayout(path_row)
        content_layout.addLayout(account_row)
        content_layout.addWidget(self.summary_label)
        content_layout.addWidget(self.preview_table)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        scroll.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel)
        self.import_button = self.buttons.addButton("Import", QDialogButtonBox.ButtonRole.AcceptRole)
        self.import_button.setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(scroll)
        layout.addWidget(self.buttons)

    def showEvent(self, event) -> None:
        super().showEvent(event)
        center_and_clamp_dialog(self, self.parentWidget())

    def choose_file(self) -> None:
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "Import Holdings Spreadsheet",
            str(Path.home()),
            "Spreadsheet Files (*.csv *.xlsx);;CSV Files (*.csv);;Excel Files (*.xlsx)",
        )
        if not path:
            return
        self._load_file(Path(path))

    def accept(self) -> None:
        if not self._source_path or not self.preview_rows:
            QMessageBox.warning(self, "Nothing to Import", "Choose a CSV or XLSX file first.")
            return
        self.import_result = import_preview_rows(
            self.repository,
            self.preview_rows,
            str(self._source_path),
            self._source_path.suffix.lower().lstrip("."),
        )
        QMessageBox.information(
            self,
            "Import Complete",
            f"Imported {self.import_result.imported_count} holdings. "
            f"Skipped {self.import_result.skipped_count}.",
        )
        super().accept()

    def _populate_accounts(self) -> None:
        self.account_combo.clear()
        account_names = [account.name for account in self.repository.list_accounts()]
        if DEFAULT_ACCOUNT_NAME not in account_names:
            account_names.insert(0, DEFAULT_ACCOUNT_NAME)
        self.account_combo.addItems(account_names)
        self.account_combo.setCurrentText(DEFAULT_ACCOUNT_NAME)

    def _load_file(self, path: Path) -> None:
        try:
            self.raw_rows = read_spreadsheet(path)
        except Exception as exc:
            QMessageBox.warning(self, "Import Failed", str(exc))
            return

        self._source_path = path
        self.path_edit.setText(str(path))
        self._rebuild_preview()

    def _rebuild_preview(self) -> None:
        if not self.raw_rows:
            return
        self.preview_rows = create_import_preview(
            self.raw_rows,
            self.repository,
            self.account_combo.currentText().strip() or DEFAULT_ACCOUNT_NAME,
        )
        self._populate_preview_table()

    def _populate_preview_table(self) -> None:
        accepted = sum(1 for row in self.preview_rows if row.status == "accepted")
        skipped = len(self.preview_rows) - accepted
        self.summary_label.setText(
            f"Found {len(self.preview_rows)} rows. {accepted} ready to import, {skipped} skipped."
        )
        self.import_button.setEnabled(accepted > 0)

        self.preview_table.setRowCount(len(self.preview_rows))
        for row_index, row in enumerate(self.preview_rows):
            values = [
                str(row.row_number),
                row.status,
                row.message,
                row.account_name,
                row.symbol_name,
                str(row.shares),
                f"${row.buy_price:,.4f}",
                f"${row.target_sell_price:,.4f}",
                row.notes,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                if column in {0, 5, 6, 7}:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                self.preview_table.setItem(row_index, column, item)
        self.preview_table.resizeColumnsToContents()
