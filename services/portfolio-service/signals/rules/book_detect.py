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


def concentration(weights: Sequence[float]) -> float:
    """BK-62: sum of squared weights (Herfindahl) of a portfolio whose weights add up to 1; 1 = one asset, 1/n = evenly spread."""
    if abs(sum(weights) - 1) > 1e-6 or min(weights) < 0:
        raise ValueError("weights must be non-negative and add up to 1")
    return sum(w * w for w in weights)


def regime_20(closes: Sequence[float], move: float = 0.20) -> list[str | None]:
    """BK-40: "bull" after a rise of 20 % from the lowest close since the last peak, "bear" after a fall of 20 % from the highest."""
    out: list[str | None] = []
    state, low, high = None, float("inf"), 0.0
    for c in closes:
        low, high = min(low, c), max(high, c)
        if state != "bull" and c >= low * (1 + move):
            state, high = "bull", c
        elif state != "bear" and c <= high * (1 - move):
            state, low = "bear", c
        out.append(state)
    return out


def average_daily_range(daily: Sequence[Candle], index: int, days: int = 20) -> float | None:
    """BK-75: mean high - low of the `days` bars before `index` (the running bar is not used)."""
    return sum(c.high - c.low for c in daily[index - days:index]) / days if index >= days else None


def stop_is_far_enough(entry: float, stop: float, daily_range: float, least: float = 1.0) -> bool:
    """BK-75: a stop closer than one average daily range is inside the noise."""
    return abs(entry - stop) >= least * daily_range


def stop_beyond_round(stop: float, side: str, step: float) -> float:
    """BK-76: a stop resting just on the wrong side of a round number (within 2 % of `step`) moves to the same distance beyond it."""
    nearest, near = round(stop / step) * step, 0.02 * step
    if abs(stop - nearest) > near or (stop < nearest if side == "long" else stop > nearest):
        return stop
    return nearest - near if side == "long" else nearest + near


def extreme(values: Sequence[float], index: int, tail: float = 0.05, least: int = 200) -> str | None:
    """BK-80 / BK-81: "high" / "low" when the value lies in the top / bottom `tail` of its OWN past (bars before `index` only)."""
    past = sorted(v for v in values[:index] if v is not None)
    if len(past) < least or values[index] is None:
        return None
    k = int(tail * len(past))
    return "high" if values[index] > past[-k - 1] else "low" if values[index] < past[k] else None


def range_break(candles: Sequence[Candle], index: int, window: int = 20) -> str | None:
    """BK-101: the close of bar `index` beyond the high / low of the `window` bars before it ("up" / "down")."""
    if index < window:
        return None
    past = candles[index - window:index]
    close = candles[index].close
    return "up" if close > max(c.high for c in past) else "down" if close < min(c.low for c in past) else None


def break_holds(candles: Sequence[Candle], index: int, level: float, side: str, days: int = 3) -> bool | None:
    """BK-120: `days` closes in a row beyond the level, the break bar included. None while they are not all known."""
    if index + days > len(candles):
        return None
    return all(c.close > level if side == "up" else c.close < level for c in candles[index:index + days])


def rolling_win_share(returns: Sequence[float], length: int) -> float | None:
    """BK-135: share of all holding windows of `length` periods whose compounded return is positive."""
    windows = len(returns) - length + 1
    if length < 1 or windows < 1:
        return None
    wins = 0
    for i in range(windows):
        value = 1.0
        for r in returns[i:i + length]:
            value *= 1 + r
        wins += value > 1
    return wins / windows


def payoff_ratio(results: Sequence[float]) -> float | None:
    """BK-110: average win / average loss. None without at least one of each."""
    wins, losses = [r for r in results if r > 0], [-r for r in results if r < 0]
    return (sum(wins) / len(wins)) / (sum(losses) / len(losses)) if wins and losses else None
