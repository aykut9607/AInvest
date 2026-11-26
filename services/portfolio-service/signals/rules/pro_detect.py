"""Detectors for PROFESSIONAL.md: volume profile and naked POC, gap (FVG) fill states, SFP + MSB + retest, CME weekend gaps, absorption,
open interest / funding. Objects carry the bar from which they are known (no look-ahead).
"""

from __future__ import annotations

from bisect import bisect_left
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from signals.data.candles import Candle
from signals.rules.pa_detect import DOWN, MSB, UP, Break
from signals.rules.smc_detect import Zone
from signals.structure.sfp import BULLISH, Sfp

CHICAGO = ZoneInfo("America/Chicago")
CME_ALWAYS_ON = datetime(2026, 5, 29, 21, 30, tzinfo=timezone.utc)      # 5:30 p.m. ET: CME crypto trades 24/7 from here on


# ---------- volume profile (PR-01 ...)

@dataclass(frozen=True)
class Profile:
    start: datetime
    end: datetime             # exclusive; the profile is known from here on
    low: float
    high: float
    poc: float
    val: float
    vah: float
    volume: float
    bins: tuple[float, ...]


def volume_profile(candles: Sequence[Candle], bins: int = 60, area: float = 0.70) -> Profile | None:
    """Every candle's volume is spread evenly over its range (trade-by-trade data would be exact). POC = centre of the fullest
    bin; the value area grows from it, adding the fuller neighbour, until it holds `area` of the volume."""
    if not candles:
        return None
    low, high = min(c.low for c in candles), max(c.high for c in candles)
    if high <= low:
        return None
    step = (high - low) / bins
    volume = [0.0] * bins
    for c in candles:
        first, last = min(bins - 1, int((c.low - low) / step)), min(bins - 1, int((c.high - low) / step))
        span = c.high - c.low
        for k in range(first, last + 1):
            if span <= 0 or first == last:
                share = 1.0 / (last - first + 1)
            else:
                share = max(0.0, min(c.high, low + (k + 1) * step) - max(c.low, low + k * step)) / span
            volume[k] += c.volume * share
    total = sum(volume)
    if total <= 0:
        return None
    poc = max(range(bins), key=lambda k: volume[k])
    a = b = poc
    held = volume[poc]
    while held < area * total and (a > 0 or b < bins - 1):
        below = volume[a - 1] if a > 0 else -1.0
        above = volume[b + 1] if b < bins - 1 else -1.0
        if above >= below:
            b += 1
            held += above
        else:
            a -= 1
            held += below
    return Profile(candles[0].time, candles[-1].time, low, high, low + (poc + 0.5) * step, low + a * step, low + (b + 1) * step,
                   total, tuple(volume))


def session_profiles(candles: Sequence[Candle], days: int = 1, bins: int = 60) -> list[Profile]:
    """Profiles of consecutive UTC sessions of `days` days (7 = Monday-Sunday weeks)."""
    groups: dict[datetime, list[Candle]] = {}
    for c in candles:
        day = c.time.replace(hour=0, minute=0, second=0, microsecond=0)
        key = day - timedelta(days=day.weekday()) if days == 7 else day
        groups.setdefault(key, []).append(c)
    out = []
    for key, part in sorted(groups.items()):
        p = volume_profile(part, bins)
        if p is not None:
            out.append(Profile(key, key + timedelta(days=days), p.low, p.high, p.poc, p.val, p.vah, p.volume, p.bins))
    return out


def poc_touch(candles: Sequence[Candle], profile: Profile) -> int | None:
    """First bar after the session whose range covers the POC (from then on it is no longer naked)."""
    for i, c in enumerate(candles):
        if c.time >= profile.end and c.low <= profile.poc <= c.high:
            return i
    return None


# ---------- FVG fill states (PR-30 ...)

UNTOUCHED, PARTIAL, HALF, FULL = "dokunulmadı", "kısmi", "%50 doldu", "tam doldu"


def fill_state(candles: Sequence[Candle], zone: Zone, until: int | None = None) -> str:
    """How far price came back into the gap between its birth and bar `until` (inclusive)."""
    part = candles[zone.known_at + 1:None if until is None else until + 1]
    if not part:
        return UNTOUCHED
    if zone.direction == UP:
        depth = (zone.high - min(c.low for c in part)) / (zone.high - zone.low)
    else:
        depth = (max(c.high for c in part) - zone.low) / (zone.high - zone.low)
    return UNTOUCHED if depth < 0 else FULL if depth >= 1 else HALF if depth >= 0.5 else PARTIAL


# ---------- SFP + MSB + retest (PR-60 ...)

RETEST = (0.618, 0.66)        # the lesson's zone; its limit order sat at 0.636
ENTRY = 0.639                 # middle of the zone
STOP_BUFFER = 0.04            # beyond the SFP's extreme, as a share of the move (the lesson: 141.8 of 3,524.5 = 4.0%)


@dataclass(frozen=True)
class SfpPlan:
    sfp: Sfp                  # on the higher timeframe
    msb: Break                # first structure break in its direction on the lower timeframe
    origin: float             # 1 of the fib: the SFP's extreme
    end: float                # 0 of the fib: the furthest price before the retest = target
    touch: int                # lower-timeframe bar of the retest
    entry: float
    stop: float

    @property
    def risk_reward(self) -> float:
        return abs(self.end - self.entry) / abs(self.entry - self.stop)


def sfp_msb_plans(htf: Sequence[Candle], htf_span: timedelta, sfps: Sequence[Sfp], ltf: Sequence[Candle],
                  breaks: Sequence[Break], wait: timedelta = timedelta(days=5), retest: timedelta = timedelta(days=5)) -> list[SfpPlan]:
    """Higher-timeframe SFP (known at its candle's close) -> lower-timeframe MSB in its direction within `wait`, the extreme
    holding -> price reaches the 0.639 retracement of the move (0 follows the running extreme) within `retest` of the MSB."""
    out = []
    times = [c.time for c in ltf]
    for s in sfps:
        up = s.direction == BULLISH
        known = htf[s.confirmed_at].time + htf_span
        first = bisect_left(times, known)
        b = next((b for b in breaks if b.index >= first and times[b.index] <= known + wait and b.kind == MSB
                  and b.direction == (UP if up else DOWN)), None)
        if b is None:
            continue
        sign = 1 if up else -1
        begin = bisect_left(times, htf[s.sweep_index].time)          # the sweep itself lies before `known`
        if any(sign * (c.low if up else c.high) < sign * s.extreme for c in ltf[first:b.index + 1]):
            continue
        origin_bar = next((i for i in range(begin, b.index + 1)
                           if sign * (ltf[i].low if up else ltf[i].high) <= sign * s.extreme), begin)
        end = max(sign * (c.high if up else c.low) for c in ltf[origin_bar + 1:b.index + 1])
        for i in range(b.index + 1, len(ltf)):
            if times[i] > times[b.index] + retest:
                break
            c = ltf[i]
            against, along = sign * (c.low if up else c.high), sign * (c.high if up else c.low)
            move = end - sign * s.extreme
            if against <= end - ENTRY * move:
                entry = end - ENTRY * move
                out.append(SfpPlan(s, b, s.extreme, sign * end, i, sign * entry, sign * (sign * s.extreme - STOP_BUFFER * move)))
                break
            end = max(end, along)
    return out


# ---------- CME weekend gap (PR-50 ...)

@dataclass(frozen=True)
class WeekendGap:
    close_time: datetime      # Friday 16:00 Chicago
    open_time: datetime       # Sunday 17:00 Chicago
    close: float
    open: float
    open_index: int

    @property
    def up(self) -> bool:
        return self.open > self.close


def weekend_gaps(hourly: Sequence[Candle], min_share: float = 0.005) -> list[WeekendGap]:
    """Approximated with the spot price at CME's closing and opening hour. None from 29 May 2026 on (24/7 trading)."""
    at = {c.time: i for i, c in enumerate(hourly)}
    out = []
    for c in hourly:
        local = c.time.astimezone(CHICAGO)
        if local.weekday() != 4 or local.hour != 16 or c.time < datetime(2017, 12, 18, tzinfo=timezone.utc):
            continue
        sunday = (local + timedelta(days=2)).replace(hour=17).astimezone(timezone.utc)
        if sunday not in at or sunday >= CME_ALWAYS_ON:
            continue
        i = at[sunday]
        close, opened = c.open, hourly[i].open
        if abs(opened / close - 1) >= min_share:
            out.append(WeekendGap(c.time, sunday, close, opened, i))
    return out


def gap_filled_at(hourly: Sequence[Candle], gap: WeekendGap, level: float | None = None) -> int | None:
    """First bar from the open on that trades at the Friday close (or at `level`)."""
    level = gap.close if level is None else level
    for i in range(gap.open_index, len(hourly)):
        if hourly[i].low <= level <= hourly[i].high:
            return i
    return None


# ---------- absorption (PR-42)

def absorption(candles: Sequence[Candle], length: int = 12, flat: float = 0.25, strong: float = 2.0) -> list[tuple[int, str]]:
    """Over `length` bars the price barely moves (|change| <= flat x its range) while the summed delta is `strong` times its usual
    size. Sellers absorbed (delta strongly negative, price holds) -> UP; buyers absorbed -> DOWN."""
    if any(c.taker_buy_volume is None for c in candles):
        return []
    delta = [2 * c.taker_buy_volume - c.volume for c in candles]
    sums = [sum(delta[i - length + 1:i + 1]) if i >= length - 1 else None for i in range(len(candles))]
    out: list[tuple[int, str]] = []
    for i in range(length * 10, len(candles)):
        usual = sum(abs(s) for s in sums[i - length * 9:i]) / (length * 9)
        part = candles[i - length + 1:i + 1]
        span = max(c.high for c in part) - min(c.low for c in part)
        if usual <= 0 or span <= 0 or abs(part[-1].close - part[0].open) > flat * span or abs(sums[i]) < strong * usual:
            continue
        if not out or i - out[-1][0] > length:
            out.append((i, UP if sums[i] < 0 else DOWN))
    return out


# ---------- open interest (SM-95): price / OI quadrants

def oi_quadrant(price_change: float, oi_change: float) -> str:
    if oi_change >= 0:
        return "OI↑ fiyat↑" if price_change >= 0 else "OI↑ fiyat↓"
    return "OI↓ fiyat↑" if price_change >= 0 else "OI↓ fiyat↓"
