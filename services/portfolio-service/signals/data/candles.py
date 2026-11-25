"""Clean candles for the 4.4 rules, built from the raw files in data/raw (see download.py).

What happens between the raw files and the rules (every step deterministic and unit-tested):
  1. derived timeframes: 45m = 3 x 15m (both markets), BTC 1w = 7 x 1d (the archive's weekly files have gaps), 3d and 1M from 1d,
     futures 2h / 4h / 6h / 12h = 1h grouped into UTC blocks, futures 3d = three consecutive sessions. Buckets are aligned to UTC midnight / Monday 00:00 UTC,
     like Binance. For BTC an incomplete bucket (an exchange outage, the running week) is dropped.
  2. bad rows out: a candle whose open/close lies outside its own low-high range; gold daily/weekly before 2012
     (Yahoo's old GC=F mixes settlement closes with thin-contract highs/lows: 441 such days 2003-2011).
  3. futures roll days out of the INTRADAY data: Yahoo's continuous front-month series switches contract on
     those days and some hours mix both contracts (gold 2025-07-30: every hour's high from the new contract,
     its low from the old one, a fake ~1.8% range). Daily and weekly candles are kept (one switch, no mixing).
       S&P (ES=F): the third Friday of March, June, September, December (expiry day)
       gold (GC=F): a day in the last week of Jan/Mar/May/Jul/Sep/Nov after which the volume jumps >= 3x
       both: any day with a > 0.4% jump between back-to-back 1h candles inside a session (median gap ~0.004%)
Prices are NOT back-adjusted: the series matches an unadjusted continuous chart (TradingView GC1!/ES1! default).
"""

from __future__ import annotations

import csv
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo

from signals.data.download import RAW_DIR

ASSETS = {
    # asset -> (source folder, symbol folder)
    "BTCUSDT": ("binance", "BTCUSDT"),
    "GC": ("yahoo", "GC_F"),
    "ES": ("yahoo", "ES_F"),
    "XAU": ("histdata", "XAUUSD"),         # spot gold and S&P 500 CFD, no volume: the 15m-12h frames Yahoo lacks (histdata.py)
    "SPX": ("histdata", "SPXUSD"),
}
TIMEFRAMES = ["15m", "30m", "45m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w", "1M"]
LTF = ["15m", "30m", "45m", "1h", "2h"]               # confirmation frames (Aykut, 25 Nov)
HTF = ["4h", "6h", "12h", "1d", "3d", "1w", "1M"]     # zone and reversal frames
HOURS = {"2h": 2, "4h": 4, "6h": 6, "12h": 12}
GOLD_CLEAN_FROM = datetime(2012, 1, 1, tzinfo=timezone.utc)
ROLL_VOLUME_JUMP = 3.0
JUMP_THRESHOLD = 0.004   # 0.4% between back-to-back candles inside a session


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


def bucket_start_3d(moment: datetime) -> datetime:
    """Binance's 3-day block: counted from 1970-01-02 (checked against Binance's own 3d candles on 25 Nov 2026)."""
    days = (moment.date() - date(1970, 1, 2)).days
    return datetime(1970, 1, 2, tzinfo=timezone.utc) + timedelta(days=days - days % 3)


def bucket_start_month(moment: datetime) -> datetime:
    return moment.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def in_threes(candles: list[Candle]) -> list[Candle]:
    """Futures 3d: three consecutive sessions, counted from the first session of each year (a calendar block would
    hold one to three sessions because of weekends). The last block of a year may be shorter; a running block is kept out."""
    years: dict[int, list[Candle]] = {}
    for c in candles:
        years.setdefault(c.time.year, []).append(c)
    out = []
    for year in sorted(years):
        own = years[year]
        for k in range(0, len(own), 3):
            part = own[k:k + 3]
            if len(part) == 3 or year != max(years):
                out += resample(part, lambda t, start=part[0].time: start, None)[0]
    return out


NEW_YORK = ZoneInfo("America/New_York")


def session_date(moment: datetime) -> date:
    """Trading day of gold and the S&P: from 18:00 New York the evening before (like TradingView's daily candle)."""
    return (moment.astimezone(NEW_YORK) + timedelta(hours=6)).date()


def bucket_session(moment: datetime, minutes: int) -> datetime:
    """Start of the n-minute block counted from 18:00 New York (TradingView's 45m, 2h, 4h, 6h, 12h candles of GC1! / ES1!)."""
    local = moment.astimezone(NEW_YORK)
    elapsed = (local.hour * 60 + local.minute - 18 * 60) % 1440
    return moment - timedelta(minutes=elapsed % minutes, seconds=moment.second)


def session_start(label: datetime) -> datetime:
    """The real start of the period labelled by this trading day: 18:00 New York the evening before."""
    d = label.date() - timedelta(days=1)
    return datetime(d.year, d.month, d.day, 18, tzinfo=NEW_YORK).astimezone(timezone.utc)


def bucket_session_day(moment: datetime) -> datetime:
    d = session_date(moment)
    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


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


def jump_days(candles: list[Candle], max_step: timedelta = timedelta(hours=1), threshold: float = JUMP_THRESHOLD) -> set[date]:
    """Days with a jump between two back-to-back candles of a continuous session (no break between them).
    In a liquid, nearly 24-hour market the next candle opens at the previous close: on Yahoo's GC=F/ES=F 1h data
    the median gap is ~0.004%. A gap above 0.4% (100x the median) is a contract mix-up or a bad tick, not trading.
    example lets say gold 2025-07-30 07:00 closes 3383.0 and 08:00 opens 3383.2, 09:00 opens 3329.3 after an
    08:00 close of 3386.9 -> -1.7% inside the session -> 2025-07-30 is flagged"""
    days = set()
    for previous, current in zip(candles, candles[1:]):
        if current.time - previous.time <= max_step and previous.close > 0 \
                and abs(current.open / previous.close - 1) > threshold:
            days.add(current.time.date())
    return days


def without_days(candles: list[Candle], days: set[date]) -> tuple[list[Candle], int]:
    kept = [c for c in candles if c.time.date() not in days]
    return kept, len(candles) - len(kept)


# ---------- the series the rules use ----------

def _raw(asset: str, timeframe: str, raw_dir: Path) -> list[Candle]:
    source, folder = ASSETS[asset]
    return read_raw(raw_dir / source / folder / f"{timeframe}.csv")


def _roll_days(asset: str, raw_dir: Path) -> set[date]:
    """Days whose intraday futures candles are not trusted: the calendar/volume roll days plus every day with an
    in-session jump in the 1h data (catches the mixed-contract hours and Yahoo's occasional bad ticks; in 2026
    Yahoo switched gold contracts at the session open without mixing, so the volume rule alone missed nothing
    harmful but also found no roll there)."""
    if asset == "ES":
        calendar = es_roll_days(2000, datetime.now(timezone.utc).year + 1)
    elif asset == "GC":
        calendar = gold_roll_days(_raw("GC", "1d", raw_dir))
    else:
        return set()
    return calendar | jump_days(_raw(asset, "1h", raw_dir))


@lru_cache(maxsize=2)
def _spot_15m(asset: str, raw_dir: Path) -> tuple[Candle, ...]:
    """The newest part without a hole of more than 200 days (missing year files); weekend stubs of under two hours are left out."""
    raw = read_raw(raw_dir / "histdata" / f"{ASSETS[asset][1]}_15m.csv")
    start = max((i + 1 for i, (p, c) in enumerate(zip(raw, raw[1:])) if c.time - p.time > timedelta(days=200)), default=0)
    days: dict[date, list[Candle]] = {}
    for c in raw[start:]:
        if is_consistent(c):
            days.setdefault(session_date(c.time), []).append(c)
    return tuple(c for d in sorted(days) if d.weekday() < 5 and len(days[d]) >= 8 for c in days[d])


def frames_from_15m(candles: list[Candle], timeframe: str) -> list[Candle]:
    """Session-aligned frames of gold and the S&P."""
    if timeframe == "15m":
        return list(candles)
    minutes = {"30m": 30, "45m": 45, "1h": 60, **{f: h * 60 for f, h in HOURS.items()}}.get(timeframe)
    if minutes:
        return resample(candles, lambda m: bucket_session(m, minutes), None)[0]
    daily = resample(candles, bucket_session_day, None)[0]
    if timeframe == "1d":
        return daily
    if timeframe == "3d":
        return in_threes(daily)
    return resample(daily, bucket_start_week if timeframe == "1w" else bucket_start_month, None)[0][:-1]


def _spot(asset: str, timeframe: str, raw_dir: Path) -> Series:
    return Series(asset, timeframe, frames_from_15m(list(_spot_15m(asset, raw_dir)), timeframe), {})


def load_series(asset: str, timeframe: str, raw_dir: Path = RAW_DIR) -> Series:
    """Clean candles of one asset and timeframe, oldest first, with a count of everything left out."""
    if asset not in ASSETS or timeframe not in TIMEFRAMES:
        raise ValueError(f"Unknown asset/timeframe {asset}/{timeframe}")
    dropped: dict[str, int] = {}
    is_crypto = ASSETS[asset][0] == "binance"
    if ASSETS[asset][0] == "histdata":
        return _spot(asset, timeframe, raw_dir)
    intraday = timeframe not in ("1d", "3d", "1w", "1M")

    if timeframe == "45m":
        candles, incomplete = resample(_raw(asset, "15m", raw_dir), lambda t: bucket_start_minutes(t, 45),
                                       expected_parts=3 if is_crypto else None)
        dropped["incomplete_buckets"] = incomplete
    elif timeframe == "1w" and is_crypto:
        candles, incomplete = resample(_raw(asset, "1d", raw_dir), bucket_start_week, expected_parts=7)
        dropped["incomplete_buckets"] = incomplete
    elif timeframe in HOURS and not is_crypto:
        size = HOURS[timeframe] * 60
        candles, _ = resample(_raw(asset, "1h", raw_dir), lambda t: bucket_session(t, size), expected_parts=None)
    elif timeframe == "3d":
        daily = _raw(asset, "1d", raw_dir)
        if is_crypto:
            candles, dropped["incomplete_buckets"] = resample(daily, bucket_start_3d, expected_parts=3)
        else:
            candles = in_threes(daily)
    elif timeframe == "1M":
        daily = _raw(asset, "1d", raw_dir)
        candles, _ = resample(daily, bucket_start_month, expected_parts=None)
        candles = [c for c in candles if c.time < bucket_start_month(daily[-1].time)]      # the running month is not a candle yet
    else:
        candles = _raw(asset, timeframe, raw_dir)

    if not is_crypto and timeframe in ("1d", "1w") and (raw_dir / ASSETS[asset][0] / ASSETS[asset][1] / "1h.csv").exists():
        # Yahoo's newest daily / weekly row is the running session: not a candle yet
        newest = _raw(asset, "1h", raw_dir)[-1].time
        span = timedelta(days=1 if timeframe == "1d" else 7)
        before = len(candles)
        candles = [c for c in candles if c.time + span <= newest]
        dropped["running"] = before - len(candles)

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
