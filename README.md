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
