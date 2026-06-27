from gaingoblin.importers.spreadsheet_reader import read_spreadsheet


def test_csv_import_reads_rows(tmp_path) -> None:
    path = tmp_path / "holdings.csv"
    path.write_text(
        "Ticker,Quantity,Average Cost,Account\n"
        "ORC,10,$7.50,Robinhood Main\n"
        "VTI,2,250.25,Fidelity IRA\n",
        encoding="utf-8",
    )

    rows = read_spreadsheet(path)

    assert len(rows) == 2
    assert rows[0].row_number == 2
    assert rows[0].values["Ticker"] == "ORC"
    assert rows[1].values["Account"] == "Fidelity IRA"


def test_xlsx_import_reads_rows(tmp_path) -> None:
    from openpyxl import Workbook

    path = tmp_path / "holdings.xlsx"
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["Ticker", "Quantity", "Average Cost", "Account"])
    sheet.append(["ORC", "10", "7.50", "Robinhood Main"])
    sheet.append(["VTI", "2", "250.25", "Fidelity IRA"])
    workbook.save(path)

    rows = read_spreadsheet(path)

    assert len(rows) == 2
    assert rows[0].values["Ticker"] == "ORC"
    assert rows[1].values["Average Cost"] == "250.25"
