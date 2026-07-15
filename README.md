# Gain Goblin

Gain Goblin is a local-first manual stock profit planner inspired by Asset Goblin.
Gain Goblin is manual-first and works offline. It can optionally fetch market
information from a user-configured data provider. It does not connect to
brokerage accounts, synchronize balances, execute trades, or recommend buying
or selling. All fetched values remain reviewable and editable before use.

## Current Features

- Manual holding entry and editing
- Range Profit Calculator for manually entered high/low scenario math
- Optional Market Data Scout with Mock demo data and a working Alpha Vantage provider
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
- OS credential-store API key storage for market-data providers
- Local rotating diagnostic logs under `logs/` (no secrets)

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

- connect to brokerage accounts or request brokerage credentials
- synchronize account balances
- execute trades or provide trade controls
- recommend buying or selling
- provide investment advice or predictive claims

Online market data remains optional and disabled by default. A provider may
require an API key. Keys are stored through the operating-system credential
store (via Python `keyring`), not in settings JSON. Data freshness depends on
the provider and account plan (historical, delayed, end-of-day, or real-time).
Manual calculator operation remains fully available offline.

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

## Range Profit Calculator

Gain Goblin includes a manual range calculator for quick scenario math.

You can enter:

- ticker / symbol
- shares
- planned buy price
- average low price
- average high price
- estimated fees

Gain Goblin calculates:

- entry cost
- possible value at the entered low
- possible value at the entered high
- possible gain/loss
- ROI at the entered low/high
- break-even price
- price spread

This is not a prediction tool and does not recommend trades. It only calculates
scenarios from values the user enters.

## Market Data Scout

Gain Goblin can optionally use provider-based market-data connections for the
Range Profit Calculator. Online data is disabled by default. Manual range math
still works with no provider configured.

Provider status in v0.1.8-alpha:

- Mock — fully working local demo values (no API key)
- Alpha Vantage — fully working online quotes and daily historical bars (API key required)
- Polygon — placeholder / unavailable
- Nasdaq Data Link — placeholder / unavailable

API keys are stored through the operating-system credential store, shown only as
a masked placeholder after saving, and can be cleared from the dialog. Keys are
never written to `data/*.json`.

Market Data Scout can fetch a quote when a provider supports it, calculate
historical average high/low metrics from daily bars, show source, fetched
timestamp, freshness, lookback period, and cache status, and place fetched
values into editable Range Calculator fields. Quote cache TTL is configurable
and defaults to five minutes. Historical daily bars use a 24-hour local cache.
Network fetches run off the UI thread.

Market values may be historical, delayed, end-of-day, or real-time depending on
the provider and account plan. They are not predictions or recommendations.
Gain Goblin does not scrape Nasdaq.com, Robinhood, Yahoo Finance pages, or
brokerage pages.

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

## v0.1.5-alpha

- Added responsive breakpoints for compact, standard, and wide layouts
- Reworked clipboard UI into a clean drawn parchment workspace
- Treated fantasy art as decorative frame instead of active UI surface
- Improved clipboard artwork scaling so bundled raster art is not upscaled
- Added layered wood, parchment, and metal clip artwork for a cleaner shell
- Improved fullscreen shell flow with a wider responsive board canvas
- Cleaned generated artwork cutouts to remove visible PNG/backdrop artifacts
- Added deterministic stage geometry for fullscreen-safe board, clip, paper, and UI alignment
- Reworked action buttons with wrapping flow layout and safer minimum widths
- Increased panel/table contrast for a cleaner fantasy ledger workspace
- Added richer goblin companion event animations and reduced-motion support hook
- Grounded the goblin companion on a painted mini-stage with floor shadow and coins
- Added manifest-based goblin sprite animation loading with safe fallback rendering
- Polished import preview row colors and dialog hierarchy
- Kept imports local-only, read-only, and user-reviewed


## v0.1.6-alpha

- Added Range Profit Calculator
- Added manually entered average high/low scenario math
- Added break-even and spread calculations
- Added selected-holding preload support
- Added range calculator tests
- Kept all price inputs manual and local-only


## v0.1.7-alpha

- Added Market Data Providers architecture
- Added optional Historical Range Scout
- Added average high/low calculations from historical price bars
- Added lookback windows
- Added data source, delay label, and fetched timestamp display
- Added Alpha Vantage, Polygon, and Mock provider classes
- Added local cache and settings foundations
- Kept online data disabled by default and all fetched values editable

## v0.1.8-alpha

- Renamed Historical Range Scout to Market Data Scout
- Added quote model support with freshness labels
- Added provider metadata for quotes, historical daily bars, and real-time support
- Added local quote caching with configurable TTL
- Kept historical daily bars on a 24-hour local cache
- Implemented Alpha Vantage as the first working online provider (quotes + daily bars)
- Left Polygon and Nasdaq Data Link explicitly unavailable as placeholders
- Moved API keys into the OS credential store via `keyring`, with one-time plaintext migration
- Masked saved keys in the UI and kept Clear Saved API Key
- Added safe rotating logs under `logs/` with credential redaction
- Added GitHub Actions CI with Ruff and pytest on Python 3.11 and 3.12
- Updated Range Calculator fetch flow to populate quote, average high/low, range extremes, and volume fields while keeping every value editable
- Kept online market data optional, disabled by default, and free of brokerage sync or trading controls
