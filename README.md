# Gain Goblin

Gain Goblin is a local-first manual stock profit planner inspired by Asset Goblin.
It does not connect to brokerages, fetch live stock prices, make buy/sell
recommendations, or control trades. It only calculates values from numbers you
enter.

## Current Features

- Manual holding entry and editing
- Summary cards for total cost basis, target net value, projected profit, and ROI
- Animated lower-right goblin companion with portfolio reactions
- Clipboard-and-parchment art shell for the Gain Goblin workspace
- CSV/XLSX holdings import with local preview
- Text-based PDF holdings import with required preview
- Paste-from-clipboard/table text import with cautious parsing
- Account grouping for manually imported or entered holdings
- CSV export of entered and calculated fields
- Local SQLite persistence
- Decimal-based financial calculations

## Gain Goblin Personality

Gain Goblin is styled as a greedy little goblin treasure clerk for manual
portfolio planning.

- Goblin speech bubble reactions
- Treasure-styled summary cards
- Goblin note labels for planned return ranges
- Clipboard/parchment workspace art
- Goblin-themed status messages

## Product Boundaries

Gain Goblin does not:

- connect to brokerages
- fetch live prices
- execute trades
- recommend buying or selling
- provide investment advice

All calculations are based only on values the user manually enters.

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .[dev]
```

## Run

```powershell
python -m gaingoblin
```

## Test

```powershell
python -m pytest
```

## v0.1.1-alpha

- Added goblin-themed dark UI
- Added animated lower-right goblin companion
- Added goblin speech bubble reactions
- Added treasure-styled summary cards
- Added goblin personality logic tests

## v0.1.2-alpha

- Stabilized clipboard/parchment shell scaling
- Preserved the bundled artwork aspect ratio on large window sizes
- Added a larger goblin companion in a reserved lower-right workspace area
- Improved responsive summary card layout
- Added UI layout tests for the clipboard shell and companion area
- Kept all stock math local and manual-only

## Importing Holdings

Gain Goblin can import user-provided CSV, XLSX, text-based PDF, and pasted table/text data.

Imports are local-only. Gain Goblin does not connect to brokerage accounts,
request passwords, fetch live balances, or sync account data. PDF and pasted imports are
best-effort and always require preview before saving.

Supported import fields:

- symbol / ticker
- shares / quantity
- buy price / average cost
- optional fees
- optional target sell price
- optional account name
- optional notes

PDF limitations:

- text-based PDFs only
- scanned/image-only PDFs are not supported yet
- no OCR is included in v0.1.4-alpha

Paste import can read simple copied tables or cautious Robinhood-style text blocks,
but it does not invent missing financial values. Rows without a detected buy price
are skipped in the preview.

## v0.1.3-alpha

- Added CSV/XLSX holdings import
- Added account grouping
- Added import preview flow
- Added duplicate-skip protection
- Added import tests
- Kept all account data local and manually imported

## v0.1.4-alpha

- Added Robinhood-friendly local import options
- Added text-based PDF statement/report import using pypdf
- Added paste-from-clipboard/table text import
- Added cautious Robinhood-style text parser
- Required preview before importing PDF or pasted rows
- Kept imports local-only, read-only, and credential-free
