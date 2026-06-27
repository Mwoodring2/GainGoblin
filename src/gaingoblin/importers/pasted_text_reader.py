from __future__ import annotations

from gaingoblin.importers.import_models import RawImportRow
from gaingoblin.importers.robinhood_parser import parse_robinhood_text, parse_tabular_text


def read_pasted_text(text: str) -> list[RawImportRow]:
    clean_text = text.strip()
    if not clean_text:
        return []

    tabular_rows = parse_tabular_text(clean_text)
    if tabular_rows:
        return tabular_rows

    return parse_robinhood_text(clean_text)
