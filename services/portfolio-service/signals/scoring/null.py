"""Shuffled prices: the control of every test.

A rule's respect rate means something only next to the rate the SAME rule gets, with the same code, on prices without memory. Four-hour
blocks trade places with blocks of the same hour of the day inside windows of 90 days (daily-only futures data: 5-bar blocks inside a
year), so the volatility of the hour and of the season stays, the structure a rule could use does not. Simpler controls (random bars,
shifted levels, matched touches) were tried first and called 42-54 of 400 rules "significant" on shuffled data (8 expected): biased.
"""

from __future__ import annotations

import random

from signals.data.candles import (HOURS, TIMEFRAMES, Candle, bucket_session, frames_from_15m, bucket_start_3d, bucket_start_minutes, bucket_start_month, bucket_start_week, in_threes,
                                  load_series, resample)
from signals.scoring.reaction import SPLIT

NO_VOLUME = ("XAU", "SPX")


def shuffle(source: list[Candle], seed: int, hours: int | None) -> list[Candle]:
    """hours: block length on an intraday series; None: 5-bar blocks of a daily series. Every bar keeps its shape (open, high, low, close
    relative to the previous close, volume); only the order of the blocks changes. The times stay where they were."""
    rng = random.Random(seed)
    blocks: list[list[int]] = []
    last_key = None
    for i in range(1, len(source)):
        t = source[i].time
        key = (t.date(), t.hour // hours) if hours else i // 5
        if key != last_key:
            blocks.append([])
            last_key = key
        blocks[-1].append(i)
    start = source[0].time
    groups: dict = {}
    for n, b in enumerate(blocks):
        t = source[b[0]].time
        groups.setdefault(((t - start).days // (90 if hours else 365), t.hour if hours else 0, len(b)), []).append(n)
    place = list(range(len(blocks)))
    for members in groups.values():
        moved = members[:]
        rng.shuffle(moved)
        for a, b in zip(members, moved):
            place[a] = b
    out, last = [source[0]], source[0].close
    order = (i for n in place for i in blocks[n])
    for at, i in zip(source[1:], order):
        c, p = source[i], source[i - 1].close
        out.append(Candle(at.time, last * c.open / p, last * c.high / p, last * c.low / p, last * c.close / p, c.volume, c.taker_buy_volume))
        last *= c.close / p
    return out


def null_cache(asset: str, seed: int, piece=None) -> dict:
    """The same frames as rule_events.load_all, built from shuffled calibration data."""
    def part(frame):
        c = load_series(asset, frame).candles
        return piece(c) if piece else c[:int(len(c) * SPLIT)]

    def grouped(candles, minutes):
        return resample(candles, lambda t: bucket_start_minutes(t, minutes), None)[0]

    out = {}
    if asset in NO_VOLUME:
        base = shuffle(part("15m"), seed, 4)
        return {(asset, f): frames_from_15m(base, f) for f in TIMEFRAMES}
    if asset == "BTCUSDT":
        base = shuffle(part("15m"), seed, 4)
        out[(asset, "15m")] = base
        for frame, minutes in (("30m", 30), ("45m", 45), ("1h", 60), *((f, h * 60) for f, h in HOURS.items()), ("1d", 1440)):
            out[(asset, frame)] = grouped(base, minutes)
        daily = out[(asset, "1d")]
        out[(asset, "3d")] = resample(daily, bucket_start_3d, None)[0]
    else:
        fine, hourly, daily = shuffle(part("15m"), seed, 4), shuffle(part("1h"), seed, 4), shuffle(part("1d"), seed, None)
        out[(asset, "15m")], out[(asset, "1h")], out[(asset, "1d")] = fine, hourly, daily
        out[(asset, "30m")], out[(asset, "45m")] = grouped(fine, 30), grouped(fine, 45)
        for frame, h in HOURS.items():
            out[(asset, frame)] = resample(hourly, lambda t, m=h * 60: bucket_session(t, m), None)[0]
        out[(asset, "3d")] = in_threes(daily)
    out[(asset, "1w")] = resample(daily, bucket_start_week, None)[0]
    out[(asset, "1M")] = resample(daily, bucket_start_month, None)[0]
    return out
