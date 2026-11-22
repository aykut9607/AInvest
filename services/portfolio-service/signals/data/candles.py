"""Clean candles for the 4.4 rules, built from the raw files in data/raw (see download.py).

What happens between the raw files and the rules (every step deterministic and unit-tested):
  1. derived timeframes: 45m = 3 x 15m (both markets), BTC 1w = 7 x 1d (the archive's weekly files have gaps),
     futures 4h = 1h grouped into 4-hour UTC blocks. Buckets are aligned to UTC midnight / Monday 00:00 UTC,
     like Binance. For BTC an incomplete bucket (an exchange outage, the running week) is dropped.
  2. bad rows out: a candle whose open/close lies outside its own low-high range; gold daily/weekly before 2012
     (Yahoo's old GC=F mixes settlement closes with thin-contract highs/lows: 441 such days 2003-2011).
  3. futures roll days out of the INTRADAY data: Yahoo's continuous front-month series switches contract on
     those days and some hours mix both contracts (gold 2025-07-30: every hour's high from the new contract,
     its low from the old one, a fake ~1.8% range). Daily and weekly candles are kept (one switch, no mixing).
       S&P (ES=F): the third Friday of March, June, September, December (expiry day)
       gold (GC=F): a day in the last week of Jan/Mar/May/Jul/Sep/Nov after which the volume jumps >= 3x
Prices are NOT back-adjusted: the series matches an unadjusted continuous chart (TradingView GC1!/ES1! default).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from signals.data.download import RAW_DIR

ASSETS = {
    # asset -> (source folder, symbol folder)
    "BTCUSDT": ("binance", "BTCUSDT"),
    "GC": ("yahoo", "GC_F"),
    "ES": ("yahoo", "ES_F"),
}
TIMEFRAMES = ["15m", "30m", "45m", "1h", "4h", "1d", "1w"]
GOLD_CLEAN_FROM = datetime(2012, 1, 1, tzinfo=timezone.utc)
ROLL_VOLUME_JUMP = 3.0


@dataclass(frozen=True)
class Candle:
    time: datetime          # open time, UTC
    open: float
    high: float
    low: float
    close: float
    volume: float
    taker_buy_volume: float | None = None   # Binance only: buyer-initiated volume, CVD = sum(2 * buy - volume)


@dataclass
class Series:
    asset: str
    timeframe: str
    candles: list[Candle]
    # what was left out and why, so a backtest report can state it
    dropped: dict[str, int] = field(default_factory=dict)


# ---------- reading ----------

def read_raw(path: Path) -> list[Candle]:
    candles = []
    with path.open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            taker = row.get("taker_buy_volume")
            candles.append(Candle(
                time=datetime.fromisoformat(row["open_time"]),
                open=float(row["open"]), high=float(row["high"]), low=float(row["low"]), close=float(row["close"]),
                volume=float(row["volume"] or 0),
                taker_buy_volume=float(taker) if taker not in (None, "") else None,
            ))
    return candles


# ---------- derived timeframes ----------

def bucket_start_minutes(moment: datetime, minutes: int) -> datetime:
    """Start of the n-minute block the moment falls in, counted from UTC midnight (45 and 240 divide a day)."""
    midnight = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    elapsed = int((moment - midnight).total_seconds() // 60)
    return midnight + timedelta(minutes=elapsed - elapsed % minutes)


def bucket_start_week(moment: datetime) -> datetime:
    """Monday 00:00 UTC of the moment's week (Binance's weekly candles start on Monday)."""
    day = moment.replace(hour=0, minute=0, second=0, microsecond=0)
    return day - timedelta(days=day.weekday())


def resample(candles: Iterable[Candle], bucket_of, expected_parts: int | None) -> tuple[list[Candle], int]:
    """Group candles into larger ones: open of the first, highest high, lowest low, close of the last, summed
    volumes. With expected_parts, a bucket with fewer parts is dropped (returned as the second value)."""
    groups: dict[datetime, list[Candle]] = {}
    for candle in candles:
        groups.setdefault(bucket_of(candle.time), []).append(candle)

    result, incomplete = [], 0
    for start in sorted(groups):
        parts = sorted(groups[start], key=lambda c: c.time)
        if expected_parts is not None and len(parts) != expected_parts:
            incomplete += 1
            continue
        takers = [p.taker_buy_volume for p in parts]
        result.append(Candle(
            time=start, open=parts[0].open, high=max(p.high for p in parts), low=min(p.low for p in parts),
            close=parts[-1].close, volume=sum(p.volume for p in parts),
            taker_buy_volume=None if any(t is None for t in takers) else sum(takers),
        ))
    return result, incomplete


# ---------- quality ----------

def is_consistent(candle: Candle) -> bool:
    """A real candle's open and close lie within its own low-high range."""
    tolerance = 1e-9 * max(1.0, abs(candle.high))
    return (candle.low <= min(candle.open, candle.close) + tolerance
            and max(candle.open, candle.close) <= candle.high + tolerance)


def third_friday(year: int, month: int) -> date:
    first = date(year, month, 1)
    return first + timedelta(days=(4 - first.weekday()) % 7 + 14)


def es_roll_days(first_year: int, last_year: int) -> set[date]:
    """E-mini S&P quarterly expiry days: Yahoo's ES=F moves to the next contract on them."""
    return {third_friday(y, m) for y in range(first_year, last_year + 1) for m in (3, 6, 9, 12)}


def gold_roll_days(daily: list[Candle]) -> set[date]:
    """Days on which Yahoo's GC=F switches contract, found in the daily volume: in the last 7 days of
    Jan/Mar/May/Jul/Sep/Nov, the first day after which the volume rises at least ROLL_VOLUME_JUMP times.
    example lets say 2025-07-30 has 19,252 contracts and 2025-07-31 has 158,029 (8.2x) -> 2025-07-30"""
    days, seen_months = set(), set()
    for today, tomorrow in zip(daily, daily[1:]):
        d = today.time.date()
        month_end = (date(d.year + (d.month == 12), d.month % 12 + 1, 1) - timedelta(days=1))
        in_roll_window = d.month % 2 == 1 and (month_end - d).days < 7
        if in_roll_window and (d.year, d.month) not in seen_months and today.volume > 0 \
                and tomorrow.volume / today.volume >= ROLL_VOLUME_JUMP:
            days.add(d)
            seen_months.add((d.year, d.month))
    return days


def without_days(candles: list[Candle], days: set[date]) -> tuple[list[Candle], int]:
    kept = [c for c in candles if c.time.date() not in days]
    return kept, len(candles) - len(kept)


# ---------- the series the rules use ----------

def _raw(asset: str, timeframe: str, raw_dir: Path) -> list[Candle]:
    source, folder = ASSETS[asset]
    return read_raw(raw_dir / source / folder / f"{timeframe}.csv")


def _roll_days(asset: str, raw_dir: Path) -> set[date]:
    if asset == "ES":
        return es_roll_days(2000, datetime.now(timezone.utc).year + 1)
    if asset == "GC":
        return gold_roll_days(_raw("GC", "1d", raw_dir))
    return set()


def load_series(asset: str, timeframe: str, raw_dir: Path = RAW_DIR) -> Series:
    """Clean candles of one asset and timeframe, oldest first, with a count of everything left out."""
    if asset not in ASSETS or timeframe not in TIMEFRAMES:
        raise ValueError(f"Unknown asset/timeframe {asset}/{timeframe}")
    dropped: dict[str, int] = {}
    is_crypto = asset == "BTCUSDT"
    intraday = timeframe not in ("1d", "1w")

    if timeframe == "45m":
        candles, incomplete = resample(_raw(asset, "15m", raw_dir), lambda t: bucket_start_minutes(t, 45),
                                       expected_parts=3 if is_crypto else None)
        dropped["incomplete_buckets"] = incomplete
    elif timeframe == "1w" and is_crypto:
        candles, incomplete = resample(_raw(asset, "1d", raw_dir), bucket_start_week, expected_parts=7)
        dropped["incomplete_buckets"] = incomplete
    elif timeframe == "4h" and not is_crypto:
        candles, _ = resample(_raw(asset, "1h", raw_dir), lambda t: bucket_start_minutes(t, 240), expected_parts=None)
    else:
        candles = _raw(asset, timeframe, raw_dir)

    if asset == "GC" and not intraday:
        before = len(candles)
        candles = [c for c in candles if c.time >= GOLD_CLEAN_FROM]
        dropped["gold_before_2012"] = before - len(candles)

    if intraday and not is_crypto:
        # 45m and 4h buckets start at UTC midnight and never cross into the next day, so dropping every candle
        # dated on a roll day also drops every bucket that contains a mixed hour
        candles, removed = without_days(candles, _roll_days(asset, raw_dir))
        dropped["roll_day_candles"] = removed

    before = len(candles)
    candles = [c for c in candles if is_consistent(c)]
    dropped["inconsistent_ohlc"] = before - len(candles)

    return Series(asset=asset, timeframe=timeframe, candles=candles, dropped=dropped)


def summary(raw_dir: Path = RAW_DIR) -> list[str]:
    """One line per asset and timeframe: rows, range, what was dropped (used to check a fresh download)."""
    lines = []
    for asset in ASSETS:
        for timeframe in TIMEFRAMES:
            series = load_series(asset, timeframe, raw_dir)
            c = series.candles
            span = f"{c[0].time:%Y-%m-%d} -> {c[-1].time:%Y-%m-%d %H:%M}" if c else "empty"
            dropped = ", ".join(f"{k}={v}" for k, v in series.dropped.items() if v)
            lines.append(f"{asset:8} {timeframe:4} {len(c):>7} candles  {span}  {dropped}")
    return lines


if __name__ == "__main__":
    # .\venv\Scripts\python.exe -m signals.data.candles   -> check what the rules will see after a download
    print("\n".join(summary()))
