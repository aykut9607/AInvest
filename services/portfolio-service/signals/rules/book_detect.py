"""Detectors for the book rules (BOOKS.md). Session VWAP with deviation bands (BK-01 ...)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from math import sqrt

from signals.data.candles import Candle
from signals.rules.smc_detect import sessions


@dataclass(frozen=True)
class Vwap:
    value: float
    deviation: float          # volume-weighted standard deviation of the typical price since the anchor


def session_vwap(candles: Sequence[Candle]) -> list[Vwap]:
    """VWAP of (high + low + close) / 3, restarted at 00:00 UTC. Row i uses the bars of that day up to and including i."""
    out: list[Vwap] = []
    day, pv, ppv, volume = None, 0.0, 0.0, 0.0
    for c in candles:
        if c.time.date() != day:
            day, pv, ppv, volume = c.time.date(), 0.0, 0.0, 0.0
        price = (c.high + c.low + c.close) / 3
        pv, ppv, volume = pv + price * c.volume, ppv + price * price * c.volume, volume + c.volume
        mean = pv / volume if volume else price
        out.append(Vwap(mean, sqrt(max(0.0, ppv / volume - mean * mean)) if volume else 0.0))
    return out


def allowed_sides(close: float, vwap: Vwap, near: float = 0.5, far: float = 1.0) -> set[str]:
    """BK-03 / BK-04: nothing within `near` deviations of VWAP, the VWAP side beyond it, and from `far` deviations on also the
    trade back towards VWAP (which still needs its own signal). `near` is ours, the book only says "close to"."""
    if vwap.deviation <= 0:
        return set()
    z = (close - vwap.value) / vwap.deviation
    if abs(z) < near:
        return set()
    sides = {"long" if z > 0 else "short"}
    return sides | {"short" if z > 0 else "long"} if abs(z) >= far else sides


def room_to_vwap(entry: float, stop: float, vwap: Vwap, reward: float = 2.0) -> bool:
    """BK-05: a trade towards VWAP needs at least `reward` times its risk before VWAP is reached."""
    return (vwap.value - entry) * (entry - stop) > 0 and abs(vwap.value - entry) >= reward * abs(entry - stop)


def opening_range(candles: Sequence[Candle], day: datetime) -> tuple[float, float] | None:
    """BK-10: low and high of the first hour after the US open of that day."""
    start = sessions(datetime(day.year, day.month, day.day, tzinfo=timezone.utc))["new york"][0]
    part = [c for c in candles if 0 <= (c.time - start).total_seconds() < 3600]
    return (min(c.low for c in part), max(c.high for c in part)) if part else None


# ---------- second book: averages, Elliott oscillator, volume at a break (BK-20 ...)

def ema(values: Sequence[float], period: int) -> list[float | None]:
    """Exponential average seeded with the simple average of the first `period` values (as the book computes it)."""
    out: list[float | None] = [None] * len(values)
    if len(values) < period:
        return out
    value, k = sum(values[:period]) / period, 2 / (period + 1)
    out[period - 1] = value
    for i in range(period, len(values)):
        value = values[i] * k + value * (1 - k)
        out[i] = value
    return out


def elliott_oscillator(closes: Sequence[float], fast: int = 5, slow: int = 35) -> list[float | None]:
    """BK-27: EMA 5 - EMA 35. Its peak in wave 3 should be higher than in wave 5."""
    return [None if a is None or b is None else a - b for a, b in zip(ema(closes, fast), ema(closes, slow))]


def volume_confirms(candles: Sequence[Candle], break_index: int, retest_index: int, window: int = 20) -> bool | None:
    """BK-25: the break bar trades above the average of the bars before it and the return to the level trades below the break.
    `window` is ours. None when there is not enough history."""
    if break_index < window or retest_index <= break_index:
        return None
    usual = sum(c.volume for c in candles[break_index - window:break_index]) / window
    back = candles[break_index + 1:retest_index + 1]
    return candles[break_index].volume > usual and sum(c.volume for c in back) / len(back) < candles[break_index].volume
