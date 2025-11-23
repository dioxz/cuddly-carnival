from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, List, Optional, Sequence, Tuple

@dataclass(frozen=True)
class PriceBar:
    timestamp: datetime
    low: float
    high: float

    @property
    def day_name(self) -> str:
        return self.timestamp.strftime("%A")

    @property
    def time_of_day(self) -> str:
        return self.timestamp.strftime("%H:%M")


def fetch_hourly_bars(
    symbol: str,
    *,
    days: int = 60,
    auto_adjust: bool = True,
) -> List[PriceBar]:
    """Download hourly OHLC data for the last ``days`` using yfinance."""

    try:
        import yfinance as yf
    except ModuleNotFoundError as exc:  # pragma: no cover - import guard
        raise RuntimeError("yfinance is required for live downloads. Install it with 'pip install yfinance'.") from exc

    end = datetime.now(tz=timezone.utc)
    start = end - timedelta(days=days)
    try:
        df = yf.download(
            symbol,
            start=start,
            end=end,
            interval="1h",
            auto_adjust=auto_adjust,
            progress=False,
            threads=False,
        )
    except Exception as exc:  # pragma: no cover - defensive network guard
        raise RuntimeError(f"yfinance download failed: {exc}") from exc

    if df is None or df.empty:
        raise ValueError("No price data returned; the symbol may be invalid or data is unavailable.")

    missing = {"High", "Low"} - set(df.columns)
    if missing:
        raise ValueError(f"Missing expected columns from yfinance response: {', '.join(sorted(missing))}")

    points: List[PriceBar] = []
    for ts, row in df.iterrows():
        ts_dt = ts.to_pydatetime()
        points.append(PriceBar(timestamp=ts_dt, low=float(row["Low"]), high=float(row["High"])))

    if not points:
        raise ValueError("No hourly bars parsed from yfinance response.")

    return sorted(points, key=lambda p: p.timestamp)


def parse_price_points(path: str) -> List[PriceBar]:
    """Fallback loader for pre-downloaded CSV data."""

    points: List[PriceBar] = []
    with open(path, newline="") as f:
        reader = csv.DictReader(f)
        expected = {"timestamp", "low", "high"}
        missing = expected - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Missing required columns: {', '.join(sorted(missing))}")
        for row in reader:
            ts = datetime.fromisoformat(row["timestamp"])
            points.append(PriceBar(timestamp=ts, low=float(row["low"]), high=float(row["high"])))
    if not points:
        raise ValueError("No price points loaded for the selected filters.")
    return sorted(points, key=lambda p: p.timestamp)


def beginning_of_week(dt: datetime) -> datetime:
    return dt - timedelta(
        days=dt.weekday(),
        hours=dt.hour,
        minutes=dt.minute,
        seconds=dt.second,
        microseconds=dt.microsecond,
    )


def select_week(points: Sequence[PriceBar], week_start: datetime) -> List[PriceBar]:
    week_end = week_start + timedelta(days=7)
    return [p for p in points if week_start <= p.timestamp < week_end]


def extremes(points: Sequence[PriceBar], count: int, *, high: bool) -> List[PriceBar]:
    key = (lambda p: (-p.high, p.timestamp)) if high else (lambda p: (p.low, p.timestamp))
    return sorted(points, key=key)[:count]


def weekly_extremes(points: Sequence[PriceBar], week_start: datetime) -> Tuple[List[PriceBar], List[PriceBar]]:
    week_points = select_week(points, week_start)
    if not week_points:
        raise ValueError("No price points found for the requested week.")
    return extremes(week_points, 3, high=False), extremes(week_points, 3, high=True)


def weekly_high_low(points: Sequence[PriceBar], week_start: datetime) -> Tuple[PriceBar, PriceBar]:
    week_points = select_week(points, week_start)
    if not week_points:
        raise ValueError("No data for week starting %s" % week_start.date())
    low = min(week_points, key=lambda p: (p.low, p.timestamp))
    high = max(week_points, key=lambda p: (p.high, p.timestamp))
    return low, high


def average_minutes(times: Iterable[datetime]) -> Optional[int]:
    times = list(times)
    if not times:
        return None

    tzinfo = times[0].tzinfo
    mins = []
    for ts in times:
        aligned = ts.astimezone(tzinfo) if tzinfo and ts.tzinfo else ts
        mins.append(aligned.hour * 60 + aligned.minute)
    return round(sum(mins) / len(mins))


def format_minutes(mins: Optional[int]) -> str:
    if mins is None:
        return "N/A"
    hours, minutes = divmod(mins, 60)
    return f"{hours:02d}:{minutes:02d}"


def describe_week(week_start: datetime) -> str:
    week_end = week_start + timedelta(days=6)
    return f"{week_start.date()} to {week_end.date()}"


def analyze(points: Sequence[PriceBar], target_week: Optional[str], window_weeks: int = 12) -> None:
    latest_week_start = beginning_of_week(points[-1].timestamp)
    if target_week:
        parsed = datetime.fromisoformat(target_week)
        week_start = beginning_of_week(parsed)
    else:
        week_start = latest_week_start

    lows, highs = weekly_extremes(points, week_start)

    print(f"Weekly highs/lows for {describe_week(week_start)}\n")
    print("Top 3 lows:")
    for p in lows:
        print(f"  ${p.low:.2f} on {p.day_name} at {p.time_of_day}")

    print("\nTop 3 highs:")
    for p in highs:
        print(f"  ${p.high:.2f} on {p.day_name} at {p.time_of_day}")

    print(f"\n{window_weeks}-week window (including target week):")
    week_starts = [week_start - timedelta(weeks=i) for i in reversed(range(window_weeks))]
    low_times = []
    high_times = []
    for ws in week_starts:
        try:
            low, high = weekly_high_low(points, ws)
        except ValueError:
            print(f"  Week {describe_week(ws)}: no data available")
            continue
        low_times.append(low.timestamp)
        high_times.append(high.timestamp)
        print(
            f"  Week {describe_week(ws)}: low ${low.low:.2f} at {low.time_of_day}, "
            f"high ${high.high:.2f} at {high.time_of_day}"
        )

    avg_low = format_minutes(average_minutes(low_times))
    avg_high = format_minutes(average_minutes(high_times))
    print("\nAverage time of weekly lows:", avg_low)
    print("Average time of weekly highs:", avg_high)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Analyze weekly highs/lows and timing from hourly stock data fetched with yfinance.",
    )
    parser.add_argument("symbol", help="Ticker symbol to fetch (e.g., AAPL).")
    parser.add_argument(
        "--days",
        type=int,
        default=60,
        help="Number of calendar days of hourly data to download (default: 60, max typical intraday window).",
    )
    parser.add_argument(
        "--week",
        help="Target week start date (YYYY-MM-DD). Defaults to the last week present in the data.",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=12,
        help="Number of weeks (including target week) to average for timing analysis. Default: 12",
    )
    parser.add_argument(
        "--no-auto-adjust",
        action="store_true",
        help="Disable auto-adjustment for splits/dividends when fetching data.",
    )
    parser.add_argument(
        "--data",
        help="Optional CSV fallback with columns timestamp,low,high; skips yfinance download when provided.",
    )
    return parser


def load_points(args: argparse.Namespace) -> List[PriceBar]:
    if args.data:
        return parse_price_points(args.data)
    return fetch_hourly_bars(args.symbol, days=args.days, auto_adjust=not args.no_auto_adjust)


def main(argv: Optional[Sequence[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    points = load_points(args)
    analyze(points, args.week, window_weeks=args.window)


if __name__ == "__main__":
    main()
