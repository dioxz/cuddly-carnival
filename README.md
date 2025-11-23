# Stock weekly high/low analyzer

A Python CLI that downloads hourly intraday data (via `yfinance`), reports the top three lows/highs for a target week, and computes average times of weekly lows/highs over a rolling window.

## What it does
- Pulls up to 60 days of hourly OHLC bars for a ticker with `yfinance` (auto-adjusted by default).
- Extracts the top three lowest hourly lows and top three highest hourly highs for a selected trading week.
- Lists each week's absolute low/high across a configurable window (default: 12 weeks) and averages the time-of-day of those extremes.

## Requirements
- Python 3.11+
- [`yfinance`](https://pypi.org/project/yfinance/) installed (e.g., `pip install yfinance`). If your network blocks
  pip (common in sandboxes), the CLI will fall back to the bundled sample data automatically.

## Usage (live data)
Fetch 60 days of hourly data and analyze the most recent week:

```bash
python stock_analysis.py AAPL
```

Choose a specific target week and change the averaging window:

```bash
python stock_analysis.py AAPL --week 2024-03-18 --window 12
```

Disable auto-adjustment for splits/dividends:

```bash
python stock_analysis.py AAPL --no-auto-adjust
```

## Offline mode (CSV fallback)
You can skip live downloads by supplying a CSV with the following columns:

| column    | description                                    |
|-----------|------------------------------------------------|
| timestamp | ISO-8601 datetime (e.g., `2024-03-18T15:50:00`)|
| low       | Low price for the bar                          |
| high      | High price for the bar                         |

Example with the bundled sample dataset:

```bash
python stock_analysis.py DUMMY --data data/example_prices.csv --week 2024-03-18
```

The command prints the per-week top highs/lows followed by the averaged low/high times in HH:MM format.

If `yfinance` is unavailable (for example, pip cannot reach PyPI), the CLI emits a notice and runs against the
bundled `data/example_prices.csv` dataset so you can still verify the workflow.
