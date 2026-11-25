"""Where every testable (non-book) rule occurred, as events for reaction.measure.

TESTS is the registry: one entry = one measurable statement, tied to the rule numbers it measures. A function gets the context of one
asset and timeframe and returns its events, or (events, control) when the rule brings its own control group.
Nothing looks ahead: an event's index is the bar at which everything it uses was already known.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from functools import cached_property

import numpy as np

from signals.backtest.setups import elliott_setups, harmonic_setups
from signals.data.candles import HTF, LTF, TIMEFRAMES, Candle, load_series, session_date, session_start
from signals.indicators.cvd import cvd, cvd_divergences
from signals.indicators.rsi_divergence import (HIDDEN_BEARISH, HIDDEN_BULLISH, REGULAR_BEARISH, REGULAR_BULLISH, rsi, rsi_divergences)
from signals.patterns import harmonic
from signals.patterns.elliott import abc_counts, impulse_counts
from signals.rules import elliott_check, ext_detect, pa_detect, pro_detect, smc_detect
from signals.scoring.null import NO_VOLUME
from signals.scoring.reaction import DOWN, SPLIT, UP, Bars, Event
from signals.structure.pivots import HIGH, pivot_highs, pivot_lows
from signals.structure.sfp import BULLISH, find_open_sfps, find_sfps
from signals.structure.zigzag import zigzag

SPAN = {"15m": timedelta(minutes=15), "30m": timedelta(minutes=30), "45m": timedelta(minutes=45), "1h": timedelta(hours=1),
        "2h": timedelta(hours=2), "4h": timedelta(hours=4), "6h": timedelta(hours=6), "12h": timedelta(hours=12), "1d": timedelta(days=1),
        "3d": timedelta(days=3), "1w": timedelta(days=7), "1M": timedelta(days=31)}
PARENT = {"15m": "4h", "30m": "4h", "45m": "4h", "1h": "4h", "2h": "1d", "4h": "1d", "6h": "1d", "12h": "1d", "1d": "1w", "3d": "1w"}
INTRADAY = ["15m", "30m", "45m", "1h", "2h", "4h"]
SIGN = {"up": UP, "down": DOWN, "bullish": UP, "bearish": DOWN, "long": UP, "short": DOWN}


class Context:
    def __init__(self, asset: str, frame: str, cache: dict):
        self.asset, self.frame, self.cache = asset, frame, cache
        self.candles: list[Candle] = cache[(asset, frame)]          # calibration part only
        self.bars = Bars(self.candles)
        self.times = [c.time for c in self.candles]

    def other(self, frame: str) -> "Context | None":
        key = ("ctx", self.asset, frame)
        if key not in self.cache and len(self.cache.get((self.asset, frame), ())) > 60:
            self.cache[key] = Context(self.asset, frame, self.cache)
        return self.cache.get(key)

    def known(self, i: int) -> datetime:
        return self.times[i] + SPAN[self.frame]

    def last_closed(self, moment: datetime) -> int:
        """Last bar of this frame that was already closed at `moment`."""
        return bisect_right(self.times, moment - SPAN[self.frame]) - 1

    def bar_at(self, moment: datetime) -> int:
        """Last bar closed at or before `moment`."""
        return self.last_closed(moment)

    @cached_property
    def swings(self):
        return zigzag(self.candles, multiple=3.0)

    @cached_property
    def small(self):
        return zigzag(self.candles, multiple=1.5)

    @cached_property
    def breaks(self):
        return pa_detect.structure_breaks(self.candles, self.swings)

    @cached_property
    def trend(self) -> np.ndarray:
        """Structure direction at every bar (0 before the first break)."""
        out = np.zeros(len(self.candles), dtype=int)
        for b in self.breaks:
            out[b.index:] = SIGN[b.direction]
        return out

    def parent_trend(self, i: int) -> int:
        p = self.other(PARENT.get(self.frame, ""))
        if p is None:
            return 0
        j = p.last_closed(self.known(i))
        return int(p.trend[j]) if j >= 0 else 0

    @cached_property
    def rsi(self):
        return rsi([c.close for c in self.candles])

    @cached_property
    def divergences(self):
        return rsi_divergences(self.candles)

    @cached_property
    def cvd_div(self):
        return cvd_divergences(self.candles) if self.asset == "BTCUSDT" else []

    @cached_property
    def open_sfps(self):
        return find_open_sfps(self.candles)

    @cached_property
    def daily(self) -> list[Candle]:
        return self.cache[(self.asset, "1d")]

    def periods(self, kind: str) -> list[tuple[int, int]]:
        """(first, last) bar of every day / week / month (UTC)."""
        day = (lambda t: t.date()) if self.asset == "BTCUSDT" else session_date
        key = {"d": day, "w": lambda t: day(t).isocalendar()[:2], "m": lambda t: day(t).replace(day=1), "y": lambda t: day(t).year}[kind]
        out, start = [], 0
        for i in range(1, len(self.times)):
            if key(self.times[i]) != key(self.times[i - 1]):
                out.append((start, i - 1))
                start = i
        out.append((start, len(self.times) - 1))
        return out

    def profiles(self, kind: str):
        """Volume profiles of complete days / weeks / months, from the finest candles that cover the history."""
        key = ("vp", self.asset, kind)
        if key not in self.cache:
            fine = self.cache[(self.asset, "15m" if self.asset in ("BTCUSDT", "XAU", "SPX") else "1h")]
            groups: dict = {}
            for c in fine:
                d = c.time.date() if self.asset == "BTCUSDT" else session_date(c.time)
                t = datetime(d.year, d.month, d.day, tzinfo=c.time.tzinfo)
                start = t if kind == "d" else t - timedelta(days=t.weekday()) if kind == "w" else t.replace(day=1)
                groups.setdefault(start, []).append(c)
            out = []
            for start, part in sorted(groups.items())[1:-1]:
                p = pro_detect.volume_profile(part, bins=100)
                if p is None and self.asset not in NO_VOLUME:
                    continue
                end = start + timedelta(days=1) if kind == "d" else start + timedelta(days=7) if kind == "w" else (start + timedelta(days=32)).replace(day=1)
                if p is None:                           # no volume: only the prices of the period
                    out.append((start, end, {"HIGH": max(c.high for c in part), "LOW": min(c.low for c in part), "OPEN": part[0].open, "CLOSE": part[-1].close}))
                    continue
                total = sum(c.volume for c in part)
                vwap = sum((c.high + c.low + c.close) / 3 * c.volume for c in part) / total
                out.append((start, end, {"HIGH": p.high, "VAH": p.vah, "POC": p.poc, "VAL": p.val, "LOW": p.low, "VWAP": vwap,
                                         "OPEN": part[0].open, "CLOSE": part[-1].close}))
            if self.asset != "BTCUSDT":
                out = [(session_start(a), session_start(z), v) for a, z, v in out]
            self.cache[key] = out
        return self.cache[key]

    def ranges(self, name: str):
        """Closed Monday / week / month ranges (ext_detect) with the real moments they become known and expire."""
        found = ext_detect.reference_ranges(self.daily, name)
        return found if self.asset == "BTCUSDT" else [replace(r, known=session_start(r.known), until=session_start(r.until)) for r in found]

    def level(self, i: int, price: float, until: int | None = None) -> Event | None:
        """A level known from bar i on: support when price is above it, resistance when below."""
        if i < 0 or price == self.candles[i].close:
            return None
        return Event(i, UP if self.candles[i].close > price else DOWN, price, until)


@dataclass(frozen=True)
class Test:
    key: str
    rules: str                       # rule numbers it measures
    title: str
    frames: list[str]
    run: Callable


TESTS: list[Test] = []


def test(key: str, rules: str, title: str, frames: list[str] = TIMEFRAMES):
    def wrap(fn):
        TESTS.append(Test(key, rules, title, frames, fn))
        return fn
    return wrap


def many(entries: list[tuple], frames: list[str], maker: Callable) -> None:
    """Register one test per (key, rules, title, *arguments)."""
    for key, rules, title, *args in entries:
        TESTS.append(Test(key, rules, title, frames, lambda x, a=args: maker(x, *a)))


def clean(events) -> list[Event]:
    return [e for e in events if e is not None]


# ---------- price action

def _breaks(x: Context, kind: str):
    return [Event(b.index, SIGN[b.direction]) for b in x.breaks if b.kind == kind]


@test("bos", "PA-03", "BOS: trend yönünde kırılım (kapanış) → devam")
def _(x):
    return _breaks(x, pa_detect.BOS)


@test("msb", "PA-04 MB-02", "MSB: korunan seviyenin kırılması → yeni yönde devam")
def _(x):
    return _breaks(x, pa_detect.MSB)


@test("choch", "PA-04a SM-13", "CHoCH: iç dönüş → yeni yön")
def _(x):
    return [Event(b.index, SIGN[b.direction]) for b in pa_detect.choch_breaks(x.candles, x.swings)]


@test("msb_bos", "PA-05", "MSB + yeni yönde ilk BOS")
def _(x):
    out, armed = [], False
    for b in x.breaks:
        if b.kind == pa_detect.MSB:
            armed = True
        elif armed:
            out.append(Event(b.index, SIGN[b.direction]))
            armed = False
    return out


@test("break_htf", "PA-07 PA-08", "Kırılım üst dilim yönünde (kontrol: üst dilime karşı kırılımlar)", list(PARENT))
def _(x):
    ours, against = [], []
    for b in x.breaks:
        t = x.parent_trend(b.index)
        if t:
            (ours if t == SIGN[b.direction] else against).append(Event(b.index, SIGN[b.direction]))
    return ours, against


@test("break_retest", "PA-13 PA-23 SM-50 SM-51 SM-52 MB-05", "Kırılan seviyeye dönüş (retest / flip)")
def _(x):
    return [Event(b.index, SIGN[b.direction], b.level, b.index + 60) for b in x.breaks]


@test("bos_pullback", "PA-08", "BOS sonrası geri çekilmede trend yönü (hareketin yarısı)")
def _(x):
    out = []
    for b in x.breaks:
        if b.kind == pa_detect.BOS:
            up = b.direction == "up"
            base = min(c.low for c in x.candles[b.level_index:b.index + 1]) if up else max(c.high for c in x.candles[b.level_index:b.index + 1])
            out.append(Event(b.index, SIGN[b.direction], (base + x.candles[b.index].close) / 2, b.index + 60))
    return out


@test("trendline_touch", "PA-10 PA-14", "Üç temaslı trend çizgisine yeni dokunuş → çizgi tutar")
def _(x):
    out = []
    for t in pa_detect.trend_lines(x.candles, x.swings):
        known = t.touches[-1].confirmed_at
        last = min(len(x.candles) - 1, t.break_index if t.break_index is not None else known + 200, known + 200)
        sign = SIGN[t.direction]
        for i in range(known + 1, last + 1):
            line = t.at(i)
            if (x.candles[i].low <= line) if sign == UP else (x.candles[i].high >= line):
                out.append(Event(i - 1, sign, line, i))
                break
    return out


@test("trendline_break", "PA-12 BK-11", "Trend çizgisinin kapanışla kırılması → kırılım yönü")
def _(x):
    return [Event(t.break_index, -SIGN[t.direction]) for t in pa_detect.trend_lines(x.candles, x.swings) if t.break_index is not None]


@test("trendline_retest", "PA-13", "Kırılan trend çizgisine dönüş → kırılım yönü")
def _(x):
    return [Event(t.retest_index - 1, -SIGN[t.direction], t.at(t.retest_index), t.retest_index)
            for t in pa_detect.trend_lines(x.candles, x.swings) if t.retest_index is not None]


def _body_levels(x: Context, frame: str, taps: tuple[int, int]):
    """Levels of `frame` (bodies), by how many earlier turns of that frame sit within 0.25 ATR; tested on this frame's candles."""
    p = x.other(frame)
    if p is None:
        return []
    out, seen = [], []
    for lv in pa_detect.body_levels(p.candles):
        unit = p.bars.atr[lv.index]
        if np.isnan(unit) or lv.index + 1 >= len(p.candles):
            continue
        n = 1 + sum(abs(q - lv.price) <= 0.25 * unit for q in seen[-60:])
        seen.append(lv.price)
        if taps[0] <= n <= taps[1]:
            i = x.bar_at(p.known(lv.index + 1))
            if i >= 0:
                out.append(x.level(i, lv.price))
    return clean(out)


many([(f"body_{f}_{n}", rules, f"{f} gövde seviyesi, {label}", f, taps)
      for f in ("1M", "1w", "1d", "4h")
      for n, label, taps, rules in (("1", "ilk kez (taze)", (1, 1), "PA-20 PA-21 SM-81"), ("2", "2–3 temaslı", (2, 3), "PA-20 PA-21 PA-22"),
                                    ("4", "4+ temaslı", (4, 99), "PA-22"))],
     ["1h", "4h", "1d"], lambda x, f, taps: _body_levels(x, f, taps) if SPAN[f] > SPAN[x.frame] else [])


@test("round", "PA-24 SM-82", "Yuvarlak sayı (BTC 5.000, altın 100, S&P 100): tepki", ["15m", "1h", "4h", "1d"])
def _(x):
    step = {"BTCUSDT": 5000, "GC": 100, "XAU": 100}.get(x.asset, 100)

    def levels(offset):
        out = []
        for s, e in x.periods("w"):
            i = s - 1
            if i < 0:
                continue
            c = x.candles[i].close
            under = (c - offset) // step * step + offset
            out += [x.level(i, under, e), x.level(i, under + step, e)]
        return clean(out)
    return levels(0.0)


def _pattern(x: Context, kind: str, volume: bool | None = None, expected: int | None = None):
    out = []
    for p in pa_detect.converging_patterns(x.candles, x.swings) + pa_detect.converging_patterns(x.candles, x.small):
        if p.kind != kind or p.break_index is None:
            continue
        d = SIGN[p.break_direction]
        if expected is not None and d != expected:
            continue
        i = p.break_index
        if volume is not None:
            usual = np.mean(x.bars.volume[max(0, i - 20):i]) if i else 0
            if (x.bars.volume[i] >= 1.5 * usual) != volume:
                continue
        out.append(Event(i, d))
    return out


@test("wedge_rising", "PA-30 PA-34", "Yükselen kama, aşağı kapanış kırılımı → düşüş")
def _(x):
    return _pattern(x, pa_detect.RISING_WEDGE, expected=DOWN)


@test("wedge_falling", "PA-31 PA-34", "Alçalan kama, yukarı kapanış kırılımı → yükseliş")
def _(x):
    return _pattern(x, pa_detect.FALLING_WEDGE, expected=UP)


@test("triangle_sym", "PA-32 PA-34", "Simetrik üçgen, kapanış kırılımı → kırılım yönü")
def _(x):
    return _pattern(x, pa_detect.SYMMETRIC)


@test("diamond", "PA-33 PA-34", "Elmas, kapanış kırılımı → kırılım yönü")
def _(x):
    return [Event(d.break_index, SIGN[d.break_direction]) for d in pa_detect.diamonds(x.candles, x.swings) + pa_detect.diamonds(x.candles, x.small)
            if d.break_index is not None]


@test("pattern_volume", "PA-37", "Formasyon kırılımı hacimle (kontrol: hacimsiz kırılımlar)")
def _(x):
    names = (pa_detect.RISING_WEDGE, pa_detect.FALLING_WEDGE, pa_detect.SYMMETRIC)
    return sum((_pattern(x, n, True) for n in names), []), sum((_pattern(x, n, False) for n in names), [])


# ---------- smart money

def _candle(x: Context, name: str, htf: bool = False):
    return [Event(i, SIGN[d]) for i, n, d in smc_detect.candle_patterns(x.candles) if n == name and d]


many([("pin", "SM-01", "Pin bar yönü", smc_detect.PIN), ("engulf", "SM-02", "Engulfing yönü", smc_detect.ENGULFING)], TIMEFRAMES, _candle)


def _zones(x: Context, make, edge: str = "near", only=None):
    out = []
    for z in make(x):
        if only is not None and not only(x, z):
            continue
        up = z.direction == "up"
        price = z.mid if edge == "mid" else (z.high if up else z.low)
        out.append(Event(z.known_at, UP if up else DOWN, price))
    return out


def _fvg(x):
    return smc_detect.fair_value_gaps(x.candles, 0.25)


def _ob(x):
    return smc_detect.order_blocks(x.candles, x.swings)


many([("sd", "SM-10 SM-11 SM-12", "Arz/talep bölgesi, ilk dokunuş", lambda x: smc_detect.supply_demand(x.candles), "near"),
      ("ob", "SM-40 SM-41", "Order block, kenara ilk dokunuş", _ob, "near"),
      ("ob_mid", "SM-42", "Order block, 0,5'te giriş", _ob, "mid"),
      ("breaker", "SM-44 SM-50 SM-52", "Breaker block, ilk dönüş", lambda x: smc_detect.breakers(x.candles, x.swings), "near"),
      ("fvg", "SM-60 SM-61 PR-30", "FVG, kenara ilk dokunuş", _fvg, "near"),
      ("fvg_mid", "PR-31 SM-61", "FVG, %50 dolumda giriş", _fvg, "mid")], TIMEFRAMES, _zones)


@test("ob_htf", "SM-43", "Order block, üst dilim yönünde (kontrol: karşı yöndekiler)", list(PARENT))
def _(x):
    ours, against = [], []
    for e in _zones(x, _ob):
        t = x.parent_trend(e.index)
        if t:
            (ours if t == e.direction else against).append(e)
    return ours, against


@test("fvg_htf", "SM-61 PR-31", "FVG, üst dilim yönünde (kontrol: karşı yöndekiler)", list(PARENT))
def _(x):
    ours, against = [], []
    for e in _zones(x, _fvg):
        t = x.parent_trend(e.index)
        if t:
            (ours if t == e.direction else against).append(e)
    return ours, against


@test("range_edge", "SM-20 SM-21 MB-04", "Range ucuna dokunuş → içeri dönüş")
def _(x):
    out = []
    for r in smc_detect.ranges(x.swings) + smc_detect.ranges(x.small):
        out += [x.level(r.known_at, r.high, r.known_at + 120), x.level(r.known_at, r.low, r.known_at + 120)]
    return clean(out)


@test("deviation", "SM-22 MB-06", "Range deviasyonu (dışarı çıkıp içeri kapanış) → ters yön")
def _(x):
    return [Event(d.back_index, DOWN if d.side == HIGH else UP) for r in smc_detect.ranges(x.swings) + smc_detect.ranges(x.small)
            for d in smc_detect.deviations(x.candles, r)]


@test("range_break", "SM-23 MB-01", "Range'in gerçek kırılımı (4 kapanış dışarıda) → kırılım yönü")
def _(x):
    out = []
    for r in smc_detect.ranges(x.swings) + smc_detect.ranges(x.small):
        for i in range(r.known_at + 4, min(len(x.candles), r.known_at + 121)):
            part = [c.close for c in x.candles[i - 3:i + 1]]
            if min(part) > r.high or max(part) < r.low:
                out.append(Event(i, UP if part[0] > r.high else DOWN))
                break
    return out


@test("equal_sweep", "SM-70 SM-71 PR-25", "Eşit tepe/dip süpürülüp geri kapanış (SFP) → ters yön")
def _(x):
    out = []
    for a, p in smc_detect.equal_levels(x.candles, x.swings):
        level = max(a.price, p.price) if p.kind == HIGH else min(a.price, p.price)
        for i in range(p.confirmed_at + 1, min(len(x.candles), p.confirmed_at + 200)):
            c = x.candles[i]
            if (c.high > level) if p.kind == HIGH else (c.low < level):
                if (c.close < level) if p.kind == HIGH else (c.close > level):
                    out.append(Event(i, DOWN if p.kind == HIGH else UP))
                break
    return out


@test("ote", "SM-55 SM-56 SM-57", "OTE: son hareketin 0,705'i → hareket yönü")
def _(x):
    return _retracement(x, 0.705)


# ---------- SFP (Aykut, 25 Nov: failing volume or RSI at the sweep; if the higher frame shows none, look for it on the lower frames)

def _sfp_events(x: Context, keep=None):
    return [Event(s.confirmed_at, SIGN[s.direction]) for s in x.open_sfps if keep is None or keep(x, s)]


def _less_volume(x: Context, s) -> bool:
    return x.bars.volume[s.sweep_index] < x.bars.volume[s.pivot_index]


def _rsi_diverges(x: Context, s) -> bool:
    a, b = x.rsi[s.pivot_index], x.rsi[s.sweep_index]
    if a is None or b is None:
        return False
    return b > a if s.direction == BULLISH else b < a


class _Lower:
    """Fast lookup of lower-frame divergences: (kind) -> sorted known times with their pivot times."""

    def __init__(self, x: Context):
        self.rows = {REGULAR_BULLISH: [], REGULAR_BEARISH: []}
        for f in LTF:
            low = x.other(f) if SPAN[f] < SPAN[x.frame] else None
            if low is None:
                continue
            for d in low.divergences + low.cvd_div:
                if d.kind in self.rows:
                    self.rows[d.kind].append((low.times[d.pivot_index], low.known(d.confirmed_at)))
        for v in self.rows.values():
            v.sort()

    def known_at(self, kind: str, begin: datetime, end: datetime) -> datetime | None:
        """Earliest moment a divergence whose pivot lies in [begin, end) is known."""
        v = self.rows[kind]
        k, best = bisect_left(v, (begin,)), None
        while k < len(v) and v[k][0] < end:
            best = v[k][1] if best is None else min(best, v[k][1])
            k += 1
        return best


def _lower(x: Context) -> _Lower:
    key = ("lower", x.asset, x.frame)
    if key not in x.cache:
        x.cache[key] = _Lower(x)
    return x.cache[key]


def _sfp_lower(x: Context):
    """SFP whose sweep shows no divergence on its own frame but one on a lower frame; the event waits until both are known."""
    out = []
    for s in x.open_sfps:
        if _rsi_diverges(x, s) or _less_volume(x, s):
            continue
        k = _lower(x).known_at(REGULAR_BULLISH if s.direction == BULLISH else REGULAR_BEARISH, x.times[s.sweep_index], x.known(s.confirmed_at))
        if k is not None:
            i = max(s.confirmed_at, bisect_left(x.times, k - SPAN[x.frame]))
            if i - s.confirmed_at <= 3 and i < len(x.candles):
                out.append(Event(i, SIGN[s.direction]))
    return out


class _Higher:
    """Divergences of the frames above: (kind) -> (known, valid until)."""

    def __init__(self, x: Context):
        self.rows = {REGULAR_BULLISH: [], REGULAR_BEARISH: []}
        for f in TIMEFRAMES:
            h = x.other(f) if SPAN[f] > SPAN[x.frame] else None
            for d in (h.divergences + h.cvd_div) if h else ():
                if d.kind in self.rows:
                    k = h.known(d.confirmed_at)
                    self.rows[d.kind].append((k, k + 5 * SPAN[f]))

    def active(self, kind: str, moment: datetime) -> bool:
        return any(a <= moment <= b for a, b in self.rows[kind])


def _sfp_with(x: Context, where: str):
    """Aykut, 25 Nov: after an SFP (any frame) look at the divergences, on any frame.
    low: on a lower frame, at the sweep or within 3 bars after it; after: only those whose pivot comes after the SFP's close;
    high: on a higher frame, known at most 5 of its bars ago; any: own frame, lower or higher."""
    out, lower = [], _lower(x)
    key = ("higher", x.asset, x.frame)
    if key not in x.cache:
        x.cache[key] = _Higher(x)
    for s in x.open_sfps:
        kind = REGULAR_BULLISH if s.direction == BULLISH else REGULAR_BEARISH
        close, at = x.known(s.confirmed_at), []
        if where in ("low", "any", "after"):
            begin = close if where == "after" else x.times[s.sweep_index]
            k = lower.known_at(kind, begin, close + 3 * SPAN[x.frame])
            if k is not None:
                at.append(max(s.confirmed_at, bisect_left(x.times, k - SPAN[x.frame])))
        if where in ("high", "any") and x.cache[key].active(kind, close):
            at.append(s.confirmed_at)
        if where == "any" and _rsi_diverges(x, s):
            at.append(s.confirmed_at)
        i = min(at, default=None)
        if i is not None and i <= s.confirmed_at + 5 and i < len(x.candles):
            out.append(Event(i, SIGN[s.direction]))
    return out


many([("sfp_low_any", "SM-30 SM-32 PR-21", "SFP + alt dilimde (15m–2h) RSI/CVD uyumsuzluğu: süpürmede ya da 3 mum içinde (Aykut)", "low"),
      ("sfp_after", "SM-30 SM-32 PR-21", "SFP + kapanışından SONRA gelen alt dilim uyumsuzluğu (Aykut)", "after"),
      ("sfp_high", "SM-30 SM-32 PR-21", "SFP + üst dilimde aktif RSI/CVD uyumsuzluğu (Aykut)", "high"),
      ("sfp_any", "SM-30 SM-32 PR-21", "SFP + herhangi bir dilimde uyumsuzluk (Aykut)", "any")], TIMEFRAMES, _sfp_with)


@test("sfp", "SM-30 SM-31 SM-32 PR-60a", "SFP (geçilmemiş tepe/dip süpürülüp geri kapanış)")
def _(x):
    return _sfp_events(x)


@test("sfp_last", "SM-30", "SFP, yalnız son tepe/dip")
def _(x):
    return [Event(s.confirmed_at, SIGN[s.direction]) for s in find_sfps(x.candles)]


@test("sfp_volume", "SM-30 SM-32", "SFP + süpürmede hacim eski tepeden düşük (Aykut)")
def _(x):
    return _sfp_events(x, _less_volume)


@test("sfp_rsi", "SM-30 SM-32", "SFP + aynı dilimde RSI uyumsuz (Aykut)")
def _(x):
    return _sfp_events(x, _rsi_diverges)


@test("sfp_both", "SM-30 SM-32", "SFP + hacim ve RSI birlikte uyumsuz (Aykut)")
def _(x):
    return _sfp_events(x, lambda y, s: _less_volume(y, s) and _rsi_diverges(y, s))


@test("sfp_none", "SM-30", "SFP, kendi diliminde hiçbir uyumsuzluk yok")
def _(x):
    return _sfp_events(x, lambda y, s: not _less_volume(y, s) and not _rsi_diverges(y, s))


@test("sfp_lower", "SM-30 SM-32 PR-21", "SFP kendi diliminde uyumsuz değil ama 15m–2h'de RSI/CVD uyumsuz (Aykut)", HTF)
def _(x):
    return _sfp_lower(x)


@test("sfp_htf", "SM-32 PR-61", "SFP üst dilim yönünde (kontrol: karşı yöndekiler)", list(PARENT))
def _(x):
    ours, against = [], []
    for e in _sfp_events(x):
        t = x.parent_trend(e.index)
        if t:
            (ours if t == e.direction else against).append(e)
    return ours, against


# ---------- profile and key levels

PROFILE = ("HIGH", "VAH", "POC", "VAL", "LOW", "VWAP", "OPEN", "CLOSE")
PERIOD = {"d": "Önceki gün", "w": "Önceki hafta", "m": "Önceki ay"}
LEVEL_RULES = {"HIGH": "SM-80 MB-21", "LOW": "SM-80 MB-21", "VAH": "PR-01 PR-03", "VAL": "PR-01 PR-03", "POC": "PR-01 PR-03", "VWAP": "MB-11 SM-82",
               "OPEN": "SM-80", "CLOSE": "SM-80"}


def _previous(x: Context, kind: str, name: str):
    """The level of the period that just ended, valid during the next one."""
    out, span = [], {"d": timedelta(days=1), "w": timedelta(days=7), "m": timedelta(days=31)}[kind]
    for start, end, values in x.profiles(kind):
        i, last = x.bar_at(end), bisect_left(x.times, end + span) - 1
        if 0 <= i < last:
            out.append(x.level(i, values[name], last))
    return clean(out)


many([(f"prev_{k}_{n}", LEVEL_RULES[n], f"{PERIOD[k]} {n}", k, n) for k in PERIOD for n in PROFILE], ["15m", "1h", "4h"], _previous)


def _naked(x: Context, kind: str):
    out, span = [], {"d": timedelta(days=1), "w": timedelta(days=7), "m": timedelta(days=31)}[kind]
    bars_per_day = timedelta(days=1) / SPAN[x.frame]
    for start, end, values in x.profiles(kind):
        a, z = x.bar_at(end), x.bar_at(end + span)
        if a < 0 or z <= a or z >= len(x.candles) - 1:
            continue
        poc = values["POC"]
        if any(c.low <= poc <= c.high for c in x.candles[a + 1:z + 1]):
            continue                                                      # touched within the next period: not naked any more
        out.append(x.level(z, poc, z + int(bars_per_day * {"d": 60, "w": 180, "m": 365}[kind])))
    return clean(out)


many([("npoc_d", "PR-10 PR-11", "Günlük nPOC (en az bir gün dokunulmamış)", "d"), ("npoc_w", "PR-10 PR-11", "Haftalık nPOC", "w"),
      ("npoc_m", "PR-10 PR-11", "Aylık nPOC", "m")], ["15m", "1h", "4h"], _naked)


def _value_area(x: Context, kind: str):
    """Price opens outside the previous value area and closes back inside: the far border is the target (VAL -> POC -> VAH)."""
    out, span = [], {"d": timedelta(days=1), "w": timedelta(days=7), "m": timedelta(days=31)}[kind]
    for start, end, v in x.profiles(kind):
        i, last = x.bar_at(end), bisect_left(x.times, end + span) - 1
        if not 0 <= i < last:
            continue
        close = x.candles[i].close
        side = UP if close < v["VAL"] else DOWN if close > v["VAH"] else 0
        if not side:
            continue
        for j in range(i + 1, last + 1):
            if v["VAL"] < x.candles[j].close < v["VAH"]:
                out.append(Event(j, side))
                break
    return out


many([(f"va_{k}", "PR-04", f"{PERIOD[k]} değer alanına geri dönüş (VAL→POC→VAH ve tersi)", k) for k in PERIOD], ["15m", "1h", "4h"], _value_area)


def _val_poc_vah(x: Context, kind: str, near: float):
    """Aykut, 25 Nov: VAL and POC lie close together, price accumulates between them (4 closes in a row) and then closes beyond the
    POC -> VAH (mirror: VAH, POC -> VAL). Respect here = the far border is reached before the near border."""
    out, span = [], {"d": timedelta(days=1), "w": timedelta(days=7), "m": timedelta(days=31)}[kind]
    for start, end, v in x.profiles(kind):
        i, last = x.bar_at(end), bisect_left(x.times, end + span) - 1
        if not 0 <= i < last:
            continue
        size = v["VAH"] - v["VAL"]
        for side, edge, far in ((UP, v["VAL"], v["VAH"]), (DOWN, v["VAH"], v["VAL"])):
            if abs(v["POC"] - edge) > near * size:
                continue
            row = 0
            for j in range(i + 1, last + 1):
                c = x.candles[j].close
                if min(edge, v["POC"]) <= c <= max(edge, v["POC"]):
                    row += 1
                elif row >= 4 and side * (c - v["POC"]) > 0 and side * (far - c) > 0:
                    out.append(Event(j, side, until=last, target=far, stop=edge))
                    break
                else:
                    row = 0
    return out


many([(f"valpoc_{k}", "PR-04 PR-03", f"{PERIOD[k]}: VAL–POC yakın, arada birikim, POC üstü kapanış → VAH (ve tersi); saygı = VAH, VAL'den önce", k, 0.4) for k in PERIOD],
     ["15m", "30m", "1h", "2h", "4h"], _val_poc_vah)


def _opens(x: Context, kind: str):
    out = []
    for s, e in x.periods(kind):
        if e - s > 6:
            wait = s + (e - s) // 10                                       # the level needs price to have left it first
            out.append(x.level(wait, x.candles[s].open, e))
    return clean(out)


many([("open_w", "SM-80 MB-21", "Hafta açılışına (WO) dönüş", "w"), ("open_m", "SM-80 MB-21", "Ay açılışına (MO) dönüş", "m"),
      ("open_y", "SM-80 MB-21", "Yıl açılışına (YO) dönüş", "y")], ["1h", "4h", "1d"], _opens)


@test("mondays", "SM-80 MB-21 FM-01", "Pazartesi yüksek/düşük seviyesi (Salı–Pazar)", ["15m", "1h", "4h"])
def _(x):
    out = []
    for r in x.ranges("Pazartesi"):
        i, last = x.bar_at(r.known), bisect_left(x.times, r.until) - 1
        if 0 <= i < last:
            out += [x.level(i, r.high, last), x.level(i, r.low, last)]
    return clean(out)


def _bias(x: Context, kind: str, after: int):
    """Price above / below the period's open after `after` days: the rest of the period goes that way."""
    out = []
    for s, e in x.periods(kind):
        i = x.bar_at(x.times[s].replace(hour=0, minute=0) + timedelta(days=after))
        if s < i < e:
            out.append(Event(i, UP if x.candles[i].close > x.candles[s].open else DOWN))
    return out


many([("bias_w", "MB-09 MB-22", "Salı açılışında WO üstünde/altında → o yön", "w", 1),
      ("bias_m", "MB-09", "Ayın 6. günü MO üstünde/altında → o yön", "m", 5)], ["1h", "4h", "1d"], _bias)


@test("monday_half", "FM-03a", "Pazartesi kapanışından sonra 0,5'in üstünde/altında → o yön", ["1h", "4h"])
def _(x):
    out = []
    for r in x.ranges("Pazartesi"):
        i = x.bar_at(r.known + timedelta(days=1))
        if 0 <= i < len(x.candles) and x.times[i] < r.until:
            out.append(Event(i, UP if x.candles[i].close > (r.high + r.low) / 2 else DOWN))
    return out


def _ext(x: Context, name: str, kind: str):
    return [Event(e.index, (DOWN if e.side == HIGH else UP) * (1 if kind == ext_detect.SWEEP else -1))
            for e in ext_detect.ext_events(x.candles, x.ranges(name)) if e.kind == kind]


many([(f"ext_{n}_{k}", "MB-20 FM-02 FM-03 FM-05" if n == "Pazartesi" else "MB-20", f"{n} 1,114–1,214 bandı: {label}", n, kind)
      for n in ("Pazartesi", "Hafta", "Ay")
      for k, kind, label in (("sweep", ext_detect.SWEEP, "banda değip içeri kapanış → ters yön"), ("break", ext_detect.BREAK, "bandın ötesinde kapanış → devam"))],
     ["15m", "1h", "4h"], _ext)


@test("po3", "SM-90 SM-91 SM-92 FM-00", "Power of 3: Londra'da tek uç süpürüldü → New York ters yön", ["15m", "30m", "1h"])
def _(x):
    return [Event(p.known_at, DOWN if p.swept == HIGH else UP) for p in smc_detect.power_of_3(x.candles)]


# ---------- oscillators and volume flow

def _div(x: Context, kind: str, source: str):
    rows = x.divergences if source == "RSI" else x.cvd_div
    sign = UP if kind in (REGULAR_BULLISH, HIDDEN_BULLISH) else DOWN
    return [Event(d.confirmed_at, sign) for d in rows if d.kind == kind]


many([(f"{s.lower()}_{n}", rules, f"{s} {label}", kind, s)
      for s, base in (("RSI", "PR-20 PR-21"), ("CVD", "PR-40"))
      for n, label, kind, rules in (("pu", "pozitif uyumsuzluk (P.U) → yukarı", REGULAR_BULLISH, base), ("nu", "negatif uyumsuzluk (N.U) → aşağı", REGULAR_BEARISH, base),
                                    ("tdb", "Trend Devam (gizli boğa) → yukarı", HIDDEN_BULLISH, base), ("tda", "Trend Devam (gizli ayı) → aşağı", HIDDEN_BEARISH, base))],
     TIMEFRAMES, _div)


def _volume_div(x: Context, up: bool):
    """Higher high (lower low) between two pivots with less volume at the second: the price-volume mismatch."""
    values = [c.low if up else c.high for c in x.candles]
    ps = pivot_lows(values) if up else pivot_highs(values)
    out = []
    for a, b in zip(ps, ps[1:]):
        if 5 <= b.index - a.index <= 60 and (b.value < a.value if up else b.value > a.value) and x.bars.volume[b.index] < x.bars.volume[a.index]:
            out.append(Event(b.confirmed_at, UP if up else DOWN))
    return out


many([("vol_pu", "E-18 PA-37", "Fiyat–hacim uyumsuzluğu dipte (yeni dip, az hacim) → yukarı", True),
      ("vol_nu", "E-18 PA-37", "Fiyat–hacim uyumsuzluğu tepede (yeni tepe, az hacim) → aşağı", False)], TIMEFRAMES, _volume_div)


@test("absorption", "PR-42", "Emilim (fiyat yerinde, delta güçlü) → ters yön")
def _(x):
    return [Event(i, SIGN[d]) for i, d in pro_detect.absorption(x.candles)] if x.asset == "BTCUSDT" else []


@test("chaos", "MB-10", "Kaos fitili (dev fitil, küçük gövde, hacim) → fitil ucuna dönüş")
def _(x):
    out = []
    for i in range(20, len(x.candles)):
        c, span = x.candles[i], x.candles[i].high - x.candles[i].low
        if span < 2.5 * x.bars.atr[i - 1] or abs(c.close - c.open) > 0.25 * span or c.volume < 2 * np.mean(x.bars.volume[i - 20:i]):
            continue
        low, high = min(c.open, c.close) - c.low, c.high - max(c.open, c.close)
        if max(low, high) >= 0.6 * span:
            out.append(Event(i, DOWN if low > high else UP))
    return out


def _oi_rows(name: str, cache: dict):
    if ("oi", name) not in cache:
        from signals.data import derivatives
        rows = derivatives.load(name)
        cache[("oi", name)] = ([t for t, _ in rows], [v for _, v in rows])
    return cache[("oi", name)]


def _oi(x: Context, price_up: bool, oi_up: bool, expected: int):
    if x.asset != "BTCUSDT":
        return []
    t, v = _oi_rows("oi_1h", x.cache)
    out, step = [], 6
    for i in range(step + 20, len(x.candles), 1):
        a, b = bisect_right(t, x.known(i - step)) - 1, bisect_right(t, x.known(i)) - 1
        if a < 0 or b <= a or x.known(i) - t[b] > timedelta(hours=3):
            continue
        move = (x.candles[i].close - x.candles[i - step].close) / x.bars.atr[i]
        change = v[b] / v[a] - 1
        if abs(move) >= 2 and abs(change) >= 0.02 and (move > 0) == price_up and (change > 0) == oi_up:
            out.append(Event(i, expected))
    return out


many([("oi_uu", "SM-95", "OI↑ fiyat↑ → yukarı devam", True, True, UP), ("oi_du", "SM-95", "OI↑ fiyat↓ → aşağı devam", False, True, DOWN),
      ("oi_ud", "SM-95", "OI↓ fiyat↑ → aşağı (zayıf yükseliş)", True, False, DOWN), ("oi_dd", "SM-95", "OI↓ fiyat↓ → yukarı (zayıf düşüş)", False, False, UP)],
     ["1h", "4h", "1d"], _oi)


def _funding(x: Context, high: bool):
    if x.asset != "BTCUSDT":
        return []
    t, v = _oi_rows("funding", x.cache)
    out, armed = [], True
    for when, rate in zip(t, v):
        hot = rate >= 0.0005 if high else rate <= -0.0005
        if hot and armed:
            i = x.bar_at(when)
            if i >= 0:
                out.append(Event(i, DOWN if high else UP))
        armed = not hot
    return out


many([("fund_hi", "PR-70 SM-96", "Funding ≥ +%0,05 → aşağı", True), ("fund_lo", "PR-70 SM-96", "Funding ≤ −%0,05 → yukarı", False)], ["1h", "4h", "1d"], _funding)


# ---------- Fibonacci

CONTROL_RATIOS = (0.29, 0.44, 0.56, 0.75, 0.83)


def _retracement(x: Context, *ratios: float):
    out = []
    for a, b in zip(x.swings, x.swings[1:]):
        for r in ratios:
            price = b.price + r * (a.price - b.price)
            out.append(Event(b.confirmed_at, UP if b.kind == HIGH else DOWN, price))
    return out


many([(f"fr_{r}", rules, f"Fib geri çekilme {str(r).replace('.', ',')} → hareket yönü", r)
      for r, rules in ((0.236, "FR-02"), (0.34, "FR-02 F-03"), (0.382, "FR-02 F-03 E-10"), (0.5, "FR-02 E-10"), (0.618, "FR-02 FR-04 MB-08 E-10"), (0.66, "FR-02 FR-04 MB-08"),
                       (0.709, "FR-02 FR-04"), (0.786, "FR-02"), (0.886, "FR-02 FT-08"), (1.0, "FR-03"))]
     + [("fr_none", "FR-02", "Karşılaştırma: fib OLMAYAN oranlar (0,29 · 0,44 · 0,56 · 0,75 · 0,83)", *CONTROL_RATIOS)],
     TIMEFRAMES, lambda x, *r: _retracement(x, *r))


def _extension(x: Context, *ratios: float):
    """Trend fib 0-1-2 on three swings: reaction at the extension, against the move."""
    out = []
    for p0, p1, p2 in zip(x.swings, x.swings[1:], x.swings[2:]):
        up = p1.kind == HIGH
        if (p2.price <= p0.price) if up else (p2.price >= p0.price):
            continue
        for r in ratios:
            price = p2.price + r * (p1.price - p0.price)
            if price > 0:
                out.append(Event(p2.confirmed_at, DOWN if up else UP, price))
    return out


many([(f"ft_{r}", "FT-06 FT-07 FM-04" if r > 1.3 else "FT-02 E-11", f"Trend fib {str(r).replace('.', ',')} → tepki", r)
      for r in (0.618, 1.0, 1.272, 1.414, 1.618, 2.0, 2.618, 3.618)]
     + [("ft_none", "FT-06", "Karşılaştırma: fib OLMAYAN uzatmalar (0,8 · 1,15 · 1,5 · 1,8 · 2,3 · 3,1)", 0.8, 1.15, 1.5, 1.8, 2.3, 3.1)],
     TIMEFRAMES, lambda x, *r: _extension(x, *r))


@test("ft_trigger", "FT-02 FT-03", "Trend fib: 1,272 ötesinde kapanış → hareket yönünde devam")
def _(x):
    out = []
    for p0, p1, p2 in zip(x.swings, x.swings[1:], x.swings[2:]):
        up = p1.kind == HIGH
        if (p2.price <= p0.price) if up else (p2.price >= p0.price):
            continue
        sign = 1 if up else -1
        level = p2.price + 1.272 * (p1.price - p0.price)
        for i in range(p2.confirmed_at, min(len(x.candles), p2.confirmed_at + 200)):
            if sign * (x.candles[i].low if up else x.candles[i].high) < sign * p2.price:
                break
            if sign * x.candles[i].close > sign * level:
                out.append(Event(i, SIGN["up" if up else "down"]))
                break
    return out


@test("ft_green", "FT-04 FT-05", "Trend fib yeşil bölge: ≥ 1,414'e ulaşıp 0,786'ya dönüş → hareket yönü")
def _(x):
    out = []
    for p0, p1, p2, p3 in zip(x.swings, x.swings[1:], x.swings[2:], x.swings[3:]):
        size = p1.price - p0.price
        sign = 1 if size > 0 else -1
        if sign * p2.price <= sign * p0.price or (p3.price - p2.price) / size < 1.414:
            continue
        out.append(Event(p3.confirmed_at, sign, p2.price + 0.786 * size))
    return out


# the reshort / relong idea: a higher-frame fib zone that a lower frame confirms

def _zone_confirmed(x: Context, lo: float, hi: float, inside: bool):
    """Lower-frame divergences (this frame) whose pivot lies inside the parent frame's retracement band lo-hi, in the move's direction."""
    p = x.other(PARENT.get(x.frame, ""))
    if p is None:
        return []
    legs = [(b.confirmed_at, a, b) for a, b in zip(p.swings, p.swings[1:])]
    known = [p.known(k) for k, _, _ in legs]
    out = []
    for d in x.divergences + x.cvd_div:
        if d.kind not in (REGULAR_BULLISH, REGULAR_BEARISH):
            continue
        k = bisect_right(known, x.times[d.pivot_index]) - 1
        if k < 0:
            continue
        _, a, b = legs[k]
        want = UP if b.kind == HIGH else DOWN
        if want != (UP if d.kind == REGULAR_BULLISH else DOWN):
            continue
        r = (b.price - d.price) / (b.price - a.price)
        if inside == (lo <= r <= hi):
            out.append(Event(d.confirmed_at, want))
    return out


many([(f"zone_{n}", "FR-02 F-06 H-20 PR-21", f"Üst dilim fib bölgesi {label} + bu dilimde RSI/CVD uyumsuzluğu (kontrol: bölge dışındaki uyumsuzluklar)", lo, hi)
      for n, label, lo, hi in (("034", "0,34–0,382", 0.32, 0.40), ("050", "0,5", 0.47, 0.53), ("golden", "0,618–0,66", 0.60, 0.68),
                               ("sell", "0,709–0,786", 0.69, 0.80), ("886", "0,886", 0.86, 0.91), ("any", "0,34–0,886", 0.32, 0.91))],
     LTF, lambda x, lo, hi: (_zone_confirmed(x, lo, hi, True), _zone_confirmed(x, lo, hi, False)))


# ---------- Elliott and harmonic zones

def _setups(x: Context, make, word: str):
    return [Event(s.known_at, SIGN[s.direction], s.zone.low if s.direction == "short" else s.zone.high)
            for s in make(x.candles, x.swings, x.asset, x.frame) if word in s.rule]


many([("e_w5", "E-13 E-14 E-71 E-97", "Elliott 5. dalga bölgesi (itki) → ters tepki", elliott_setups, "wave-5 zone (impulse)"),
      ("e_w5d", "E-20 E-29", "Elliott 5. dalga bölgesi (diyagonal) → ters tepki", elliott_setups, "wave-5 zone (diagonal)"),
      ("e_zig", "E-33 E-34 E-81", "Zigzag C bölgesi → ana yöne dönüş", elliott_setups, "C zone (zigzag)"),
      ("e_flat", "E-41 E-42", "Yassı C bölgesi → ana yöne dönüş", elliott_setups, "C zone (flat)")]
     + [(f"h_{n.replace(' ', '')}", "H-04 H-21 H-24", f"Harmonik {n} PRZ → dönüş", harmonic_setups, f"Harmonic {n} PRZ")
        for n in ("Gartley", "Bat", "Alternate Bat", "Butterfly", "Crab", "Deep Crab")]
     + [("h_all", "H-08 H-20 H-21 H-22", "Harmonik, bütün formasyonlar: PRZ → dönüş", harmonic_setups, "Harmonic ")], TIMEFRAMES, _setups)


def _after_count(x: Context, kind: str):
    """A completed count (its last swing confirmed): reaction against the last leg; control: every other confirmed swing."""
    ends = set()
    if kind == "impulse":
        ends = {c.points[-1].index for c in impulse_counts(x.swings) if c.complete}
    elif kind == "abc":
        ends = {c.points[-1].index for c in abc_counts(x.swings) if len(c.points) == 4}
    else:
        check = {"triangle": elliott_check.check_triangle, "diagonal": elliott_check.check_diagonal}[kind]
        for k in range(len(x.swings) - 5):
            run = x.swings[k:k + 6]
            if check([p.price for p in run], [p.index for p in run]).possible:
                ends.add(run[-1].index)
    ours, rest = [], []
    for p in x.swings:
        (ours if p.index in ends else rest).append(Event(p.confirmed_at, DOWN if p.kind == HIGH else UP))
    return ours, rest


many([("e_done", "E-05", "Tamamlanmış 5 dalga → ters yön (kontrol: dalga sayılmayan dönüşler)", "impulse"),
      ("e_abc", "E-31 E-32 E-40", "Tamamlanmış ABC → ana yöne devam (kontrol: diğer dönüşler)", "abc"),
      ("e_diag", "E-20 E-24 E-26 E-27", "Tamamlanmış daralan diyagonal → dönüş (kontrol: diğer dönüşler)", "diagonal"),
      ("e_tri", "E-50 E-51 E-52 E-56", "Tamamlanmış üçgen → çıkış (kontrol: diğer dönüşler)", "triangle")], TIMEFRAMES, _after_count)


@test("pr60", "PR-60 PR-60a PR-60b MB-05", "HTF SFP → LTF MSB → 0,618–0,66 dönüşü → SFP yönü", ["1h"])
def _(x):
    htf = x.other("1d")
    if htf is None:
        return []
    plans = pro_detect.sfp_msb_plans(htf.candles, SPAN["1d"], htf.open_sfps, x.candles, x.breaks)
    return [Event(p.touch - 1, SIGN[p.sfp.direction], p.entry, p.touch) for p in plans]


def _halves(x: Context, events, keep):
    """(events kept, the others as the rule's own control)"""
    ours = [e for e in events if keep(e)]
    return ours, [e for e in events if not keep(e)]


@test("e_w4", "E-12 E-96", "Elliott 4. dalga: 3'ün 0,382'sine dönüş → 5 yönü (1'in alanına girmeden)")
def _(x):
    out = []
    for p0, p1, p2, p3 in zip(x.swings, x.swings[1:], x.swings[2:], x.swings[3:]):
        s = 1 if p1.kind == HIGH else -1
        w1, w3 = s * (p1.price - p0.price), s * (p3.price - p2.price)
        level = p3.price - s * 0.382 * w3
        if s * p2.price > s * p0.price and s * p3.price > s * p1.price and s * level > s * p1.price and w3 >= w1:
            out.append(Event(p3.confirmed_at, s, level))
    return out


@test("e_trunc", "E-16 E-17", "[3] > 2,618 × [1]: 5. dalga 3'ün tepesini geçemez (güdük) → ters tepki")
def _(x):
    out = []
    for p0, p1, p2, p3, p4 in zip(x.swings, x.swings[1:], x.swings[2:], x.swings[3:], x.swings[4:]):
        s = 1 if p1.kind == HIGH else -1
        w1, w3 = s * (p1.price - p0.price), s * (p3.price - p2.price)
        if s * p2.price > s * p0.price and s * p4.price > s * p1.price and w3 > 2.618 * w1:
            out.append(Event(p4.confirmed_at, -s, p3.price))
    return out


@test("e_rsi", "E-19 E-18", "Tamamlanmış 5 dalga + 3'ten 5'e RSI uyumsuz → ters yön (kontrol: uyumsuz olmayan itkiler)")
def _(x):
    ours, rest = [], []
    for c in impulse_counts(x.swings):
        if not c.complete:
            continue
        a, b = x.rsi[c.points[3].index], x.rsi[c.points[5].index]
        if a is None or b is None:
            continue
        up = c.points[5].kind == HIGH
        (ours if (b < a) == up else rest).append(Event(c.points[5].confirmed_at, DOWN if up else UP))
    return ours, rest


@test("e_channel", "E-80", "Elliott kanalı: 2–4 çizgisinin 3'ten paraleline dokunuş → ters tepki (5. dalga)")
def _(x):
    out = []
    for p1, p2, p3, p4 in zip(x.swings[1:], x.swings[2:], x.swings[3:], x.swings[4:]):
        s = 1 if p1.kind == HIGH else -1
        if not (s * p3.price > s * p1.price and s * p4.price > s * p1.price):
            continue
        slope = (p4.price - p2.price) / (p4.index - p2.index)
        for i in range(p4.confirmed_at + 1, min(len(x.candles), p4.confirmed_at + 120)):
            line = p3.price + slope * (i - p3.index)
            if (x.candles[i].high >= line) if s == 1 else (x.candles[i].low <= line):
                out.append(Event(i - 1, -s, line, i))
                break
    return out


@test("h_htf", "H-25", "Harmonik PRZ üst dilim yönünde (kontrol: karşı yöndekiler)", list(PARENT))
def _(x):
    return _halves(x, [e for e in _setups(x, harmonic_setups, "Harmonic ") if x.parent_trend(e.index)], lambda e: x.parent_trend(e.index) == e.direction)


@test("pattern_target", "PA-35", "Formasyon kırılımı → yükseklik kadar hedef, karşı çizgiden önce")
def _(x):
    out = []
    for p in pa_detect.converging_patterns(x.candles, x.swings) + pa_detect.converging_patterns(x.candles, x.small):
        if p.break_index is None:
            continue
        d, i = SIGN[p.break_direction], p.break_index
        broken, other = p.line("upper" if d == UP else "lower", i), p.line("lower" if d == UP else "upper", i)
        close = x.candles[i].close
        target = broken + d * p.height
        if d * (target - close) > 0 and d * (close - other) > 0:
            out.append(Event(i, d, until=i + 120, target=target, stop=other))
    return out


@test("fvg_chain", "PR-32", "FVG zincirinde en derindeki FVG (kontrol: zincirin en yenisi)")
def _(x):
    ours, rest, chain = [], [], []
    for z in _fvg(x) + [None]:
        if z is not None and chain and z.direction == chain[-1].direction and z.index - chain[-1].index <= 10:
            chain.append(z)
            continue
        if len(chain) >= 2:
            for which, target in ((chain[0], ours), (chain[-1], rest)):
                up = which.direction == "up"
                target.append(Event(chain[-1].known_at, UP if up else DOWN, which.high if up else which.low))
        chain = [z] if z is not None else []
    return ours, rest


# one hard rule at a time: runs that keep every rule against runs that break only this one

def _one_rule(x: Context, rule: str):
    ours, rest = [], []
    for k in range(len(x.swings) - 5):
        run = x.swings[k:k + 6]
        s = 1 if run[1].kind == HIGH else -1
        p = [s * q.price for q in run]
        w1, w3, w5 = p[1] - p[0], p[3] - p[2], p[5] - p[4]
        ok = {"E-01": p[2] > p[0], "E-02": p[3] > p[1], "E-03": not (w3 < w1 and w3 < w5), "E-04": p[4] > p[1]}
        e = Event(run[5].confirmed_at, -s)
        if all(ok.values()):
            ours.append(e)
        elif not ok[rule] and sum(ok.values()) == 3:
            rest.append(e)
    return ours, rest


many([(f"one_{r}", r, f"{r} tek başına: 5 dalga kuralların hepsine uyuyor → ters yön (kontrol: yalnız {r}'i bozanlar)", r)
      for r in ("E-01", "E-02", "E-03", "E-04")], TIMEFRAMES, _one_rule)


def _one_ratio(x: Context, rule: str):
    """Harmonic X-A-B-C: every condition kept against only this one broken; reaction at the pattern's D level."""
    ours, rest = [], []
    for k in range(len(x.swings) - 3):
        run = x.swings[k:k + 4]
        s = 1 if run[1].kind == HIGH else -1
        v = [s * q.price for q in run]
        xa, ab, bc = v[1] - v[0], v[1] - v[2], v[3] - v[2]
        if min(xa, ab, bc) <= 0:
            continue
        for spec in harmonic.SPECS:
            d = v[1] - spec.d * xa
            cd = v[3] - d
            if cd <= 0:
                continue
            ok = {"H-01": harmonic.in_range(bc / ab, *harmonic.C_RANGE), "H-03": harmonic._b_ok(spec, ab / xa),
                  "H-05": harmonic.in_range(cd / bc, *spec.bc), "H-07": cd >= 0.97 * ab}
            if s * d <= 0:
                continue
            e = Event(run[3].confirmed_at, s, s * d)
            if all(ok.values()):
                ours.append(e)
            elif not ok[rule] and sum(ok.values()) == 3:
                rest.append(e)
    return ours, rest


many([(f"one_{r}", r, f"{r} tek başına: harmonik koşulların hepsi tutuyor → D'de dönüş (kontrol: yalnız {r} tutmayanlar)", r)
      for r in ("H-01", "H-03", "H-05", "H-07")], TIMEFRAMES, _one_ratio)


def load_all(asset: str, piece=None) -> dict:
    """Calibration part (first SPLIT) of every frame of one asset."""
    cache = {}
    for frame in TIMEFRAMES:
        candles = load_series(asset, frame).candles
        cache[(asset, frame)] = piece(candles) if piece else candles[:int(len(candles) * SPLIT)]
    return cache
