"""Candles up to this moment. BTC: the local archive plus Binance's public market-data endpoint (no key, no account, read-only).

Gold and the S&P have no free live 15m source yet, so they end where the local files end (replay only).
"""

from __future__ import annotations

import json
import urllib.request
from datetime import datetime, timedelta, timezone

from signals.data.candles import TIMEFRAMES, Candle, bucket_start_3d, bucket_start_minutes, bucket_start_month, bucket_start_week, load_series, resample

URL = "https://data-api.binance.vision/api/v3/klines"
FETCHED = {"15m": 15, "30m": 30, "1h": 60, "2h": 120, "4h": 240, "6h": 360, "12h": 720, "1d": 1440}
LIVE_ASSETS = ("BTCUSDT",)
# bars kept per frame: enough for the rules (300-600 bars back, levels of the last months), few enough to rebuild at every close
KEEP = {"15m": 12000, "30m": 6000, "45m": 4000, "1h": 4000, "2h": 3000, "4h": 3000, "6h": 2000, "12h": 1500, "1d": 1500, "3d": 1000, "1w": 600, "1M": 300}


def parse(rows: list, now: datetime) -> list[Candle]:
    """Binance kline rows -> closed candles only (close time in the past)."""
    out = []
    for r in rows:
        if int(r[6]) < now.timestamp() * 1000:
            out.append(Candle(datetime.fromtimestamp(int(r[0]) / 1000, timezone.utc), float(r[1]), float(r[2]), float(r[3]), float(r[4]), float(r[5]), float(r[9])))
    return out


def fetch(symbol: str, frame: str, start: datetime, now: datetime, get=None) -> list[Candle]:
    get = get or _get
    out: list[Candle] = []
    step = timedelta(minutes=FETCHED[frame])
    while start < now:
        rows = parse(get(f"{URL}?symbol={symbol}&interval={frame}&startTime={int(start.timestamp() * 1000)}&limit=1000"), now)
        if not rows:
            break
        out += rows
        start = rows[-1].time + step
        if len(rows) < 900:
            break
    return out


def _get(url: str) -> list:
    with urllib.request.urlopen(url, timeout=10) as response:          # noqa: S310  (fixed https host)
        return json.load(response)


def joined(old: list[Candle], new: list[Candle]) -> list[Candle]:
    last = old[-1].time if old else datetime.min.replace(tzinfo=timezone.utc)
    return old + [c for c in new if c.time > last]


class Feed:
    """Keeps the candles of one asset and refreshes them; `candles()` gives the scanner's cache with only closed bars plus forming HTF bars."""

    def __init__(self, asset: str, get=None):
        self.asset, self._get = asset, get
        self.data = {f: list(load_series(asset, f).candles) for f in FETCHED}

    def refresh(self, now: datetime) -> None:
        if self.asset not in LIVE_ASSETS:
            return
        for f in FETCHED:
            self.data[f] = joined(self.data[f], fetch(self.asset, f, self.data[f][-1].time + timedelta(minutes=FETCHED[f]), now, self._get))

    def hole(self) -> str | None:
        """A message when the newest 15m bars are not continuous: a scan on broken data is worse than no scan."""
        c = self.data["15m"][-500:]
        gaps = [a.time for a, b in zip(c, c[1:]) if b.time - a.time != timedelta(minutes=15)]
        return f"missing 15m candles after {gaps[-1]:%Y-%m-%d %H:%M}" if gaps else None

    def cache(self) -> dict:
        d = {f: list(v) for f, v in self.data.items()}
        d["45m"] = resample(d["15m"], lambda t: bucket_start_minutes(t, 45), 3)[0]
        d["3d"] = resample(d["1d"], bucket_start_3d, 3)[0]
        d["1w"] = resample(d["1d"], bucket_start_week, 7)[0]
        base = d["15m"]
        d["1M"] = [c for c in resample(d["1d"], bucket_start_month, None)[0] if c.time < bucket_start_month(base[-1].time)]
        for f in TIMEFRAMES:          # a bar that is still forming is needed as the last bar of every higher frame
            if f != "15m":
                d[f] = _with_forming(d[f], base, f)
        return {(self.asset, f): d[f][-KEEP[f]:] for f in TIMEFRAMES}


def start_of(t: datetime, frame: str) -> datetime:
    if frame == "1M":
        return bucket_start_month(t)
    if frame == "1w":
        return bucket_start_week(t)
    day = t.replace(hour=0, minute=0, second=0, microsecond=0)
    if frame == "1d":
        return day
    if frame == "3d":
        return bucket_start_3d(t)
    return bucket_start_minutes(t, 45 if frame == "45m" else FETCHED[frame])


def _with_forming(bars: list[Candle], base: list[Candle], frame: str) -> list[Candle]:
    """The closed bars plus one built from the 15m candles of the period that is still open."""
    begin = start_of(base[-1].time, frame)
    if bars and bars[-1].time >= begin:
        return bars
    part = []
    for c in reversed(base):
        if c.time < begin:
            break
        part.append(c)
    part.reverse()
    buy = None if any(c.taker_buy_volume is None for c in part) else sum(c.taker_buy_volume for c in part)
    return bars + [Candle(begin, part[0].open, max(c.high for c in part), min(c.low for c in part), part[-1].close, sum(c.volume for c in part), buy)]
