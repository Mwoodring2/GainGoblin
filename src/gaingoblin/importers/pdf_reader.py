from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gaingoblin.importers.import_models import RawImportRow
from gaingoblin.importers.robinhood_parser import parse_robinhood_text

IMAGE_ONLY_MESSAGE = "This PDF looks image-only. OCR is not supported yet."
NO_ROWS_MESSAGE = "No likely holdings rows were found in this PDF."


@dataclass(frozen=True, slots=True)
class PdfReadResult:
    rows: list[RawImportRow]
    message: str = ""
    extracted_text: str = ""


def read_pdf(path: Path | str) -> PdfReadResult:
    source = Path(path)
    try:
        from pypdf import PdfReader
    except ModuleNotFoundError as exc:
        raise RuntimeError("PDF import requires pypdf. Install GainGoblin with PDF support.") from exc

    reader = PdfReader(str(source))
    page_text: list[str] = []
    for page in reader.pages:
        page_text.append(page.extract_text() or "")
    text = "\n".join(page_text).strip()

    if not text:
        return PdfReadResult(rows=[], message=IMAGE_ONLY_MESSAGE, extracted_text="")

    rows = parse_robinhood_text(text)
    if not rows:
        return PdfReadResult(rows=[], message=NO_ROWS_MESSAGE, extracted_text=text)

    return PdfReadResult(rows=rows, message=f"Found {len(rows)} possible holdings rows.", extracted_text=text)


def read_pdf_holdings(path: Path | str) -> list[RawImportRow]:
    return read_pdf(path).rows
