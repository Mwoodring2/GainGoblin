from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gaingoblin.importers.import_models import RawImportRow
from gaingoblin.importers.robinhood_parser import (
    extract_holdings_section_text,
    parse_robinhood_text,
)

IMAGE_ONLY_MESSAGE = "This PDF looks image-only. OCR is not supported yet."
NO_HOLDINGS_SECTION_MESSAGE = "No likely holdings section was found in this PDF."
NO_IMPORTABLE_HOLDINGS_MESSAGE = (
    "No importable holdings found. Try paste import, a holdings/positions page, or manual quick entry."
)


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

    holdings_text = extract_holdings_section_text(text)
    if holdings_text is None:
        return PdfReadResult(rows=[], message=NO_HOLDINGS_SECTION_MESSAGE, extracted_text=text)

    rows = parse_robinhood_text(holdings_text)
    if not rows:
        return PdfReadResult(rows=[], message=NO_IMPORTABLE_HOLDINGS_MESSAGE, extracted_text=text)

    return PdfReadResult(rows=rows, message=f"Found {len(rows)} possible holdings rows.", extracted_text=text)


def read_pdf_holdings(path: Path | str) -> list[RawImportRow]:
    return read_pdf(path).rows
