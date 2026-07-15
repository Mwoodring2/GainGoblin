from decimal import Decimal

from gaingoblin.database import HoldingRepository
from gaingoblin.importers.holdings_importer import create_import_preview, import_preview_rows
from gaingoblin.importers.pdf_reader import (
    IMAGE_ONLY_MESSAGE,
    NO_HOLDINGS_SECTION_MESSAGE,
    NO_IMPORTABLE_HOLDINGS_MESSAGE,
    read_pdf,
)


def test_pdf_text_extraction_returns_raw_rows(tmp_path) -> None:
    path = tmp_path / "statement.pdf"
    write_text_pdf(
        path,
        [
            "Robinhood Holdings",
            "AAPL Apple Inc. 10 shares Average cost $150.00",
            "MSFT Microsoft 5 shares Average cost $320.00",
        ],
    )

    result = read_pdf(path)
    preview = create_import_preview(result.rows)

    assert len(result.rows) == 2
    assert preview[0].symbol_name == "AAPL"
    assert preview[0].shares == Decimal("10")
    assert preview[0].buy_price == Decimal("150.00")


def test_empty_or_image_only_pdf_returns_helpful_message(tmp_path) -> None:
    path = tmp_path / "blank.pdf"
    write_blank_pdf(path)

    result = read_pdf(path)

    assert result.rows == []
    assert result.message == IMAGE_ONLY_MESSAGE


def test_pdf_import_batch_records_source_type_pdf(tmp_path) -> None:
    path = tmp_path / "statement.pdf"
    write_text_pdf(path, ["Positions", "AAPL Apple Inc. 10 shares Average cost $150.00"])
    repository = HoldingRepository(tmp_path / "gaingoblin.sqlite")
    preview = create_import_preview(read_pdf(path).rows, repository)

    result = import_preview_rows(repository, preview, str(path), "pdf")

    assert result.imported_count == 1
    assert repository.list_import_batches()[0].source_type == "pdf"


def test_pdf_with_only_activity_rows_returns_no_holdings_section_message(tmp_path) -> None:
    path = tmp_path / "activity.pdf"
    write_text_pdf(
        path,
        [
            "Account Activity",
            "Cash Div: R/D 06/01 P/D 06/15 4 shares at $0.11 Margin CDIV",
            "ACH deposit pending",
        ],
    )

    result = read_pdf(path)

    assert result.rows == []
    assert result.message == NO_HOLDINGS_SECTION_MESSAGE


def test_pdf_holdings_section_ignores_activity_rows(tmp_path) -> None:
    path = tmp_path / "mixed.pdf"
    write_text_pdf(
        path,
        [
            "Holdings",
            "Cash Div: R/D 06/01 P/D 06/15 4 shares at $0.11 Margin CDIV",
            "AAPL Apple Inc. 10 shares Average cost $150.00",
        ],
    )

    result = read_pdf(path)

    assert len(result.rows) == 1
    assert result.rows[0].values["Ticker"] == "AAPL"


def test_pdf_holdings_section_without_importable_rows_has_stronger_message(tmp_path) -> None:
    path = tmp_path / "empty_holdings.pdf"
    write_text_pdf(path, ["Holdings", "Cash Div: R/D 06/01 P/D 06/15 CDIV"])

    result = read_pdf(path)

    assert result.rows == []
    assert result.message == NO_IMPORTABLE_HOLDINGS_MESSAGE


def write_text_pdf(path, lines: list[str]) -> None:
    text_lines = ["BT", "/F1 12 Tf", "72 720 Td"]
    for index, line in enumerate(lines):
        if index:
            text_lines.append("0 -16 Td")
        text_lines.append(f"({_escape_pdf_text(line)}) Tj")
    text_lines.append("ET")
    stream = "\n".join(text_lines).encode("latin-1")
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 4 0 R >> >> /MediaBox [0 0 612 792] /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"\nendstream",
    ]
    _write_pdf(path, objects)


def write_blank_pdf(path) -> None:
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /Resources << >> /MediaBox [0 0 612 792] >>",
    ]
    _write_pdf(path, objects)


def _write_pdf(path, objects: list[bytes]) -> None:
    chunks = [b"%PDF-1.4\n"]
    offsets: list[int] = []
    position = len(chunks[0])
    for index, payload in enumerate(objects, start=1):
        obj = f"{index} 0 obj\n".encode("ascii") + payload + b"\nendobj\n"
        offsets.append(position)
        chunks.append(obj)
        position += len(obj)

    xref_offset = position
    xref = [f"xref\n0 {len(objects) + 1}\n".encode("ascii"), b"0000000000 65535 f \n"]
    for offset in offsets:
        xref.append(f"{offset:010d} 00000 n \n".encode("ascii"))
    trailer = (
        b"trailer\n"
        + f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii")
        + b"startxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    path.write_bytes(b"".join(chunks + xref + [trailer]))


def _escape_pdf_text(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
