r"""Confirmations at turning points (Aykut's method, 25 Nov).

  .\venv\Scripts\python.exe -m signals.scoring.turns            -> data/reports/turns.json

Every confirmed pivot (5 bars each side) of 15m, 1h, 4h and 1d is a candidate top / bottom. At each one we list which confirmations were
present there (known by the time the pivot is confirmed, nothing from the future) and then look at the 15m candles that follow:

  worked   price moved at least THRESHOLD x ATR(1d) away from the top (bottom) before the top (bottom) was exceeded, inside WINDOW
  move     the largest move away from the top (bottom) before it was exceeded or the window ended, in percent
  after    the same counted from the close at which the pivot was confirmed (what a trader could still take)

A confirmation is judged against the candidates of the same kind that did NOT have it. Confirmations of one idea form a group (Elliott,
harmonic, ...); a group counts once, its members are also listed one by one.
"""

from __future__ import annotations

import json
import sys
from bisect import bisect_left, bisect_right
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from signals.data.candles import TIMEFRAMES, Candle, load_series, resample
from signals.indicators.rsi_divergence import (HIDDEN_BEARISH, HIDDEN_BULLISH, REGULAR_BEARISH, REGULAR_BULLISH)
from signals.patterns import elliott as ew, harmonic
from signals.rules import elliott_check, pa_detect, smc_detect
from signals.scoring.null import NO_VOLUME
from signals.scoring.rule_events import SPAN, Context
from signals.scoring.run import OUT
from signals.structure.pivots import HIGH, LOW, pivot_highs, pivot_lows
from signals.structure.sfp import find_open_sfps
from signals.structure.zigzag import SwingPoint, zigzag

ASSETS = ("BTCUSDT", "XAU", "SPX")
BASES = ("15m", "1h", "4h", "1d")
THRESHOLD = {"15m": 0.25, "1h": 0.5, "4h": 1.0, "1d": 2.0}            # x ATR(1d); BTC: about 1, 2, 4, 8 percent
WINDOW = {"15m": timedelta(days=1), "1h": timedelta(days=3), "4h": timedelta(days=10), "1d": timedelta(days=40)}
TOL = 0.15                                                           # x ATR(1d): how close a level must be to the top
DIV_FRAMES = ("15m", "30m", "45m", "1h", "2h", "4h", "6h", "12h", "1d", "3d", "1w")
COUNT_FRAMES = {"15m": ("15m", "1h"), "1h": ("1h", "4h"), "4h": ("4h", "1d"), "1d": ("1d", "1w")}
FIB_BANDS = {"0,34–0,382": (0.32, 0.40), "0,5": (0.47, 0.53), "0,618–0,66": (0.60, 0.68), "0,709": (0.69, 0.73), "0,786": (0.76, 0.81), "0,886": (0.86, 0.91)}
EXTENSIONS = (1.0, 1.272, 1.414, 1.618, 2.0, 2.618, 3.618)
SPLIT = 0.7


def ts(moment: datetime) -> float:
    return moment.timestamp()


# ---------- levels: known from a moment, first touched at a moment

@dataclass
class Levels:
    """side +1: support (acts on bottoms), -1: resistance (acts on tops)"""
    known: np.ndarray
    until: np.ndarray           # the moment it is used up (first later touch) or expires
    price: np.ndarray
    side: np.ndarray

    def hit(self, side: int, when: float, price: float, tol: float) -> bool:
        return bool(((self.side == side) & (self.known < when) & (self.until >= when) & (np.abs(self.price - price) <= tol)).any())


def make_levels(rows: list[tuple[float, float, int, float | None]], path: "Path15", reuse: bool = False) -> Levels:
    """rows: (known, price, side, expiry). A level is used up by its first touch after it became known (a touch that lasts up to 12 h
    counts as one), unless `reuse`."""
    known, until, price, side = [], [], [], []
    for k, p, s, expiry in rows:
        end = expiry if expiry is not None else float("inf")
        if not reuse:
            t = path.first_touch(k, p, s, end)
            if t is not None:
                end = min(end, t + 12 * 3600)
        known.append(k), until.append(end), price.append(p), side.append(s)
    return Levels(np.array(known), np.array(until), np.array(price), np.array(side))


class Path15:
    """The 15m path every reaction is read from."""

    def __init__(self, candles):
        self.t = np.array([ts(c.time) for c in candles])
        self.high = np.array([c.high for c in candles])
        self.low = np.array([c.low for c in candles])

    def first_touch(self, known: float, price: float, side: int, end: float) -> float | None:
        i, z = int(np.searchsorted(self.t, known)), int(np.searchsorted(self.t, end)) if end != float("inf") else len(self.t)
        step = 2000
        while i < z:
            j = min(z, i + step)
            m = self.low[i:j] <= price if side == 1 else self.high[i:j] >= price
            if m.any():
                return float(self.t[i + int(m.argmax())])
            i, step = j, step * 2
        return None

    def reaction(self, start: float, end: float, extreme: float, side: int, room: float = 0.0) -> float:
        """Largest move away from `extreme` (price units) in [start, end) before it is exceeded by more than `room`. side -1: a top."""
        i, z = int(np.searchsorted(self.t, start)), int(np.searchsorted(self.t, end))
        if i >= z:
            return 0.0
        over = self.high[i:z] > extreme + room if side == -1 else self.low[i:z] < extreme - room
        if over.any():
            z = i + int(over.argmax())
            if z == i:
                return 0.0
        return float(extreme - self.low[i:z].min()) if side == -1 else float(self.high[i:z].max() - extreme)


# ---------- key levels (the panel's DAILY / WEEKLY / MONTHLY / 3M / 6M / YEARLY list)

def period_candles(daily: list[Candle], kind: str) -> list[Candle]:
    def start(t: datetime) -> datetime:
        if kind == "D":
            return t
        if kind == "W":
            return t - timedelta(days=t.weekday())
        months = {"M": 1, "3M": 3, "6M": 6, "Y": 12}[kind]
        return t.replace(month=(t.month - 1) // months * months + 1, day=1)
    base = [Candle(c.time.replace(hour=0, minute=0), c.open, c.high, c.low, c.close, c.volume) for c in daily]
    return resample(base, start, None)[0]


def key_levels(daily: list[Candle], kind: str) -> list[tuple[datetime, float, int]]:
    """Where the bodies turn: an up candle followed by a down candle that does not trade (more than 0.1 %) above it -> resistance at the
    close; mirror -> support. Known when the second candle closes."""
    cs = period_candles(daily, kind)
    out = []
    for a, b, c in zip(cs, cs[1:], cs[2:]):
        if a.close > a.open and b.close < b.open and b.high <= a.high * 1.001:
            out.append((c.time, a.close, -1))
        elif a.close < a.open and b.close > b.open and b.low >= a.low * 0.999:
            out.append((c.time, a.close, 1))
    return out


# ---------- Elliott at a provisional end point

def elliott_kinds(points: list[SwingPoint]) -> set[str]:
    """Which counts end exactly at the last (provisional) point: names of every variation found."""
    out: set[str] = set()
    price = lambda run: [p.price for p in run]
    bars = lambda run: [p.index for p in run]
    if len(points) >= 6:
        run = tuple(points[-6:])
        c = ew._impulse(run)
        if c is not None:
            out.add("bitiş diyagonali" if c.kind == ew.DIAGONAL else {ew.EXT_1ST: "itki 12345 (1. uzayan)", ew.EXT_3RD: "itki 12345 (3. uzayan)", ew.EXT_5TH: "itki 12345 (5. uzayan)"}.get(c.extension, "itki 12345 (uzamasız)"))
            s = 1 if run[1].kind == HIGH else -1
            if s * run[5].price < s * run[3].price:
                out.add("güdük 5")
        if elliott_check.check_triangle(price(run), bars(run)).possible:
            out.add("üçgen ABCDE")
    def corrective(run) -> str | None:
        a, rb = abs(run[1].price - run[0].price), abs(run[2].price - run[1].price) / max(1e-12, abs(run[1].price - run[0].price))
        s = 1 if run[1].price > run[0].price else -1
        beyond = s * run[3].price > s * run[1].price
        if rb < 0.9 and elliott_check.check_zigzag(price(run)).possible and beyond:
            return "ABC zigzag"
        if 0.9 <= rb <= 1.4:
            rc = abs(run[3].price - run[2].price) / a
            if rb <= 1.05 and 0.9 <= rc <= 1.2:
                return "ABC yassı (normal)"
            if rb > 1.0 and beyond and rc <= 2.7:
                return "ABC yassı (genişleyen)"
            if rb > 1.05 and not beyond and rc >= 0.5:
                return "ABC yassı (kaçan)"
        return None
    if len(points) >= 4:
        k = corrective(points[-4:])
        if k:
            out.add(k)
    if len(points) >= 8:
        w, y = points[-8:-4], points[-4:]
        if corrective(w) and corrective(y) and (w[1].price > w[0].price) == (y[1].price > y[0].price):
            out.add("WXY")
            if len(points) >= 12 and corrective(points[-12:-8]) and (points[-11].price > points[-12].price) == (w[1].price > w[0].price):
                out.add("WXYXZ")
    return out


def harmonic_names(points: list[SwingPoint]) -> set[str]:
    out = {p.name for p in harmonic.complete_patterns(points[-5:])} if len(points) >= 5 else set()
    if len(points) >= 4:                                                  # AB=CD on the last three legs
        a, b, c, d = points[-4:]
        ab, bc, cd = abs(b.price - a.price), abs(c.price - b.price), abs(d.price - c.price)
        if ab and 0.382 <= bc / ab <= 0.886 and abs(cd / ab - 1) <= 0.03:
            out.add("AB=CD")
    return out


class Counter_:
    """Confirmed swings of one frame and degree, with the provisional points a candidate adds."""

    def __init__(self, x: Context, multiple: float):
        self.x, self.points = x, zigzag(x.candles, multiple=multiple)
        self.known = [ts(x.known(p.confirmed_at)) for p in self.points]

    def ending_at(self, when: float, price: float, kind: str) -> list[SwingPoint]:
        """Swings known before `when`, plus the running opposite extreme if needed, plus the candidate itself."""
        n = bisect_left(self.known, when)
        pts = self.points[max(0, n - 12):n]
        j = bisect_right(self.x.times, datetime.fromtimestamp(when, timezone.utc)) - 1
        if not pts or j <= pts[-1].index:
            return []
        if pts[-1].kind == kind:                                          # the opposite leg is still unconfirmed: use its extreme so far
            part = self.x.candles[pts[-1].index + 1:j + 1]
            if not part:
                return []
            k = min(range(len(part)), key=lambda i: part[i].low) if kind == HIGH else max(range(len(part)), key=lambda i: part[i].high)
            q = part[k].low if kind == HIGH else part[k].high
            if abs(q - price) < (self.x.bars.atr[j - 1] if j else 0):
                return []
            pts = pts + [SwingPoint(LOW if kind == HIGH else HIGH, pts[-1].index + 1 + k, q, j)]
        first = pts[-1].index
        if first >= j or ((price <= pts[-1].price) if kind == HIGH else (price >= pts[-1].price)):
            return []
        b = self.x.bars                                                   # the wave ends here only if nothing after the last swing went further
        beyond = b.high[first + 1:j].max(initial=-np.inf) > price if kind == HIGH else b.low[first + 1:j].min(initial=np.inf) < price
        return [] if beyond else pts + [SwingPoint(kind, j, price, j)]


# ---------- one asset

class Confirmations:
    def __init__(self, asset: str, cache: dict):
        self.asset, self.cache = asset, cache
        self.ctx = {f: Context(asset, f, cache) for f in TIMEFRAMES if len(cache.get((asset, f), ())) > 60}
        self.path = Path15(cache[(asset, "15m")])
        d = self.ctx["1d"]
        self.day_known = [ts(d.known(i)) for i in range(len(d.candles))]
        self.volume = asset not in NO_VOLUME
        self.build_divergences()
        self.build_sfps()
        self.build_levels()
        self.counts = {(f, m): Counter_(self.ctx[f], m) for f in ("15m", "1h", "4h", "1d", "1w") if f in self.ctx for m in (2.0, 3.0)}
        self.legs = {f: zigzag(self.ctx[f].candles, multiple=3.0) for f in ("1h", "4h", "1d", "1w") if f in self.ctx}
        self.leg_known = {f: [ts(self.ctx[f].known(p.confirmed_at)) for p in v] for f, v in self.legs.items()}

    def atr_day(self, when: float) -> float:
        i = bisect_right(self.day_known, when) - 1
        v = self.ctx["1d"].bars.atr[i] if i >= 0 else np.nan
        return float(v)

    def build_divergences(self):
        """(source, frame, kind) -> sorted [(pivot time, known time, price)]"""
        self.div = {}
        for f in DIV_FRAMES:
            x = self.ctx.get(f)
            if x is None:
                continue
            rows = [("RSI", d) for d in x.divergences] + [("CVD", d) for d in (x.cvd_div if self.volume else [])]
            for src, d in rows:
                self.div.setdefault((src, f, d.kind), []).append((ts(x.times[d.pivot_index]), ts(x.known(d.confirmed_at)), d.price))
            if self.volume:
                for up in (True, False):
                    ps = (pivot_lows if up else pivot_highs)([c.low if up else c.high for c in x.candles])
                    for a, b in zip(ps, ps[1:]):
                        if 5 <= b.index - a.index <= 60 and (b.value < a.value if up else b.value > a.value) and x.bars.volume[b.index] < x.bars.volume[a.index]:
                            self.div.setdefault(("Hacim", f, REGULAR_BULLISH if up else REGULAR_BEARISH), []).append((ts(x.times[b.index]), ts(x.known(b.confirmed_at)), b.value))
        for v in self.div.values():
            v.sort()

    def build_sfps(self):
        self.sfp = {}
        for f in ("15m", "1h", "4h", "12h", "1d", "1w"):
            x = self.ctx.get(f)
            if x is not None:
                for s in find_open_sfps(x.candles):
                    i, rsi = s.sweep_index, x.rsi
                    side = 1 if s.direction == "bullish" else -1
                    weak = (rsi[i] is not None and rsi[s.pivot_index] is not None and (rsi[i] - rsi[s.pivot_index]) * side > 0) or \
                        (self.volume and x.bars.volume[i] < x.bars.volume[s.pivot_index])
                    self.sfp.setdefault((f, side), []).append((ts(x.times[i]), ts(x.known(s.confirmed_at)), weak, s.extreme))

    def build_levels(self):
        self.levels: dict[tuple[str, str], Levels] = {}
        add = lambda group, name, rows, reuse=False: self.levels.__setitem__((group, name), make_levels(rows, self.path, reuse)) if rows else None
        daily = self.cache[(self.asset, "1d")]
        for kind, name in (("D", "günlük"), ("W", "haftalık"), ("M", "aylık"), ("3M", "3 aylık"), ("6M", "6 aylık"), ("Y", "yıllık")):
            add("Key level", name, [(ts(t), p, s, None) for t, p, s in key_levels(daily, kind)])
        for f, name in (("1h", "1h"), ("4h", "4h"), ("1d", "1D"), ("1w", "1W")):                 # support that was lost (S/R flip)
            x, rows = self.ctx[f], []
            for ps, side in ((pivot_lows([c.low for c in x.candles]), -1), (pivot_highs([c.high for c in x.candles]), 1)):
                for p in ps:
                    seg = x.bars.close[p.confirmed_at + 1:p.confirmed_at + 400]
                    m = seg < p.value if side == -1 else seg > p.value
                    if m.any():
                        rows.append((ts(x.known(p.confirmed_at + 1 + int(m.argmax()))), p.value, side, None))
            add("S/R flip", name, rows)
        for f, name in (("1h", "1h"), ("4h", "4h"), ("1d", "1D")):
            x = self.ctx[f]
            for group, zones in (("order block", smc_detect.order_blocks(x.candles, x.swings)), ("FVG", smc_detect.fair_value_gaps(x.candles, 0.25)),
                                 ("arz/talep", smc_detect.supply_demand(x.candles)), ("breaker", smc_detect.breakers(x.candles, x.swings))):
                add("SMC bölge", f"{group} {name}", [(ts(x.known(z.known_at)), z.high if z.direction == "up" else z.low, 1 if z.direction == "up" else -1, None) for z in zones])
        for kind, name, days in (("d", "önceki gün", 1), ("w", "önceki hafta", 7), ("m", "önceki ay", 31)):
            x = self.ctx["15m"]
            rows: dict[str, list] = {}
            naked: list = []
            for a, z, v in x.profiles(kind):
                end, i = ts(z), x.last_closed(z)
                if i < 0:
                    continue
                for n, p in v.items():
                    rows.setdefault(n, []).append((end, p, 1 if x.candles[i].close > p else -1, end + days * 86400))
                if "POC" in v:
                    naked.append((end + days * 86400, v["POC"], z, v["POC"]))
            for n, r in rows.items():
                add("Hacim profili" if n in ("VAH", "POC", "VAL", "VWAP") else "Önceki dönem", f"{name} {n}", r, reuse=True)
            out = []
            for k, p, z, _ in naked:
                i = x.last_closed(datetime.fromtimestamp(k, timezone.utc))
                side = 1 if x.candles[i].close > p else -1
                a = int(np.searchsorted(self.path.t, ts(z))); b = int(np.searchsorted(self.path.t, k))
                if b > a and not ((self.path.low[a:b] <= p) & (self.path.high[a:b] >= p)).any():
                    out.append((k, p, side, None))
            add("Hacim profili", {"d": "nPOC günlük", "w": "nPOC haftalık", "m": "nPOC aylık"}[kind], out)
        for name in ("Pazartesi", "Hafta", "Ay"):
            rows = []
            for r in self.ctx["15m"].ranges(name):
                size = r.high - r.low
                rows += [(ts(r.known), r.high + 0.164 * size, -1, ts(r.until)), (ts(r.known), r.low - 0.164 * size, 1, ts(r.until))]
            add("EXT bandı", name, rows)
        x = self.ctx["1h"]
        for f in ("1h", "4h"):
            y, rows = self.ctx[f], []
            for r in smc_detect.ranges(y.swings) + smc_detect.ranges(y.small):
                k = ts(y.known(r.known_at))
                rows += [(k, r.high, -1, k + 120 * SPAN[f].total_seconds()), (k, r.low, 1, k + 120 * SPAN[f].total_seconds())]
            add("Range ucu", f, rows, reuse=True)
        self.lines = {}
        for f in ("1h", "4h", "1d"):
            y = self.ctx[f]
            for line in pa_detect.trend_lines(y.candles, y.swings):
                k, end = y.known(line.touches[-1].confirmed_at), y.known(line.break_index) if line.break_index is not None else None
                self.lines.setdefault((f, 1 if line.direction == "up" else -1), []).append((ts(k), ts(end) if end else float("inf"), line))
        self.candle = {f: {} for f in BASES}
        for f in BASES:
            for i, n, d in smc_detect.candle_patterns(self.ctx[f].candles):
                if d and n in (smc_detect.PIN, smc_detect.ENGULFING):
                    self.candle[f].setdefault(i, set()).add((n, 1 if d == "up" else -1))
        self.funding = ([], [])
        if self.asset == "BTCUSDT":
            from signals.data import derivatives
            rows = derivatives.load("funding")
            self.funding = ([ts(a) for a, _ in rows], [v for _, v in rows])
        step = {"BTCUSDT": 5000, "XAU": 100, "SPX": 100}[self.asset]
        self.round = step

    # ----- confirmations present at one candidate

    def at(self, base: str, side: int, t: float, known: float, price: float, atr: float) -> set[tuple[str, str]]:
        found: set[tuple[str, str]] = set()
        tol, kind = TOL * atr, HIGH if side == -1 else LOW
        regular, hidden = (REGULAR_BEARISH, HIDDEN_BEARISH) if side == -1 else (REGULAR_BULLISH, HIDDEN_BULLISH)
        b = SPAN[base].total_seconds()
        for (src, f, k), rows in self.div.items():
            if k not in (regular, hidden):
                continue
            s = SPAN[f].total_seconds()
            near = (0.02 if s <= b else TOL) * atr                        # a lower frame's pivot must be this very top
            i = bisect_left(rows, (t - s - 1,))
            ok = False
            while i < len(rows) and rows[i][0] <= t + b:
                ok |= rows[i][1] <= known and abs(rows[i][2] - price) <= near
                i += 1
            if ok:
                found.add((f"{src} uyumsuzluk" if k == regular else f"{src} Trend Devam", f))
        for (f, sd), rows in self.sfp.items():
            if sd != side:
                continue
            s = SPAN[f].total_seconds()
            near = (0.02 if s <= b else TOL) * atr
            i = bisect_left(rows, (t - s - 1,))
            while i < len(rows) and rows[i][0] <= t + b:
                if rows[i][1] <= known and abs(rows[i][3] - price) <= near:
                    found.add(("SFP", f))
                    if rows[i][2]:
                        found.add(("SFP + uyumsuzluk", f))
                i += 1
        for (group, name), lv in self.levels.items():
            if lv.hit(side, t + b, price, tol):
                found.add((group, name))
        if min(price % self.round, self.round - price % self.round) <= tol / 2:
            found.add(("Yuvarlak sayı", str(self.round)))
        x = self.ctx[base]
        j = bisect_right(x.times, datetime.fromtimestamp(t, timezone.utc)) - 1
        for i in (j, j + 1):
            for n, d in self.candle[base].get(i, ()):
                if d == side:
                    found.add(("Mum", n))
        for (f, sd), rows in self.lines.items():
            if sd == side:
                y = self.ctx[f]
                q = bisect_right(y.times, datetime.fromtimestamp(t, timezone.utc)) - 1
                if any(k < t <= end and q - line.touches[-1].index < 300 and abs(line.at(q) - price) <= tol for k, end, line in rows):
                    found.add(("Trend çizgisi", f))
        i = bisect_right(self.funding[0], t) - 1
        if i >= 0 and t - self.funding[0][i] < 9 * 3600 and -side * self.funding[1][i] >= 0.0005:
            found.add(("Funding aşırı", "BTC"))
        for f in COUNT_FRAMES[base]:
            c = self.counts.get((f, 2.0))
            pts = c.ending_at(t, price, kind) if c else []
            if len(pts) >= 5:
                shift = max(0, pts[-5].index - 1)
                run = [SwingPoint(p.kind, p.index - shift, p.price, pts[-1].index - shift) for p in pts[-5:]]
                for pat in pa_detect.converging_patterns(c.x.candles[shift:pts[-1].index + 1], run):
                    up = pat.kind == pa_detect.RISING_WEDGE
                    if pat.kind == pa_detect.SYMMETRIC or (up and side == -1) or (pat.kind == pa_detect.FALLING_WEDGE and side == 1):
                        found.add(("Kama / üçgen", pat.kind))
        for f in COUNT_FRAMES[base]:
            for m in (2.0, 3.0):
                c = self.counts.get((f, m))
                pts = c.ending_at(t, price, kind) if c else []
                if len(pts) >= 4:
                    for n in elliott_kinds(pts):
                        found.add(("Elliott", n))
                    for n in harmonic_names(pts):
                        found.add(("Harmonik", n))
        for f, legs in self.legs.items():
            n = bisect_left(self.leg_known[f], t)
            if n < 3:
                continue
            a, z = legs[n - 2], legs[n - 1]                                # the last confirmed leg a -> z
            if z.kind != kind:
                r = (price - z.price) / (a.price - z.price)
                for name, (lo, hi) in FIB_BANDS.items():
                    if lo <= r <= hi:
                        found.add((f"Fib reshort/relong {f}", name))
                p0, p1, p2 = legs[n - 3], legs[n - 2], legs[n - 1]        # trend fib: p0 -> p1 -> p2, the candidate is the far end
                if (p1.kind == kind) and ((p2.price > p0.price) if kind == HIGH else (p2.price < p0.price)):
                    e = (price - p2.price) / (p1.price - p0.price)
                    for k in EXTENSIONS:
                        if abs(e - k) <= 0.03:
                            found.add((f"Trend fib hedefi {f}", str(k).replace(".", ",")))
        return found


def candidates(x: Context, base: str):
    for ps, side in ((pivot_highs([c.high for c in x.candles]), -1), (pivot_lows([c.low for c in x.candles]), 1)):
        for p in ps:
            yield p.index, p.confirmed_at, p.value, side


def load_full(asset: str) -> dict:
    return {(asset, f): load_series(asset, f).candles for f in TIMEFRAMES}


def job(asset: str, bases: tuple[str, ...] = BASES, cache: dict | None = None) -> dict:
    cache = cache or load_full(asset)
    c = Confirmations(asset, cache)
    out = {}
    for base in bases:
        x, rows = c.ctx[base], []
        for i, conf, price, side in sorted(candidates(x, base)):
            t, known = ts(x.times[i]), ts(x.known(conf))
            atr = c.atr_day(t)
            if not atr or np.isnan(atr) or known + WINDOW[base].total_seconds() > c.path.t[-1]:
                continue
            begin = t + SPAN[base].total_seconds()
            move = c.path.reaction(begin, begin + WINDOW[base].total_seconds(), price, side)
            entry = x.candles[conf].close
            later = c.path.reaction(known, known + WINDOW[base].total_seconds(), price, side)
            gone = abs(price - entry)
            rows.append([t, side, round(100 * move / price, 3), bool(move >= THRESHOLD[base] * atr), bool(later - gone >= THRESHOLD[base] * atr),
                         round(100 * THRESHOLD[base] * atr / price, 2), sorted(f"{g}|{n}" for g, n in c.at(base, side, t, known, price, atr)),
                         round(price, 2)])
        out[base] = rows
    return out


def seeded(asset: str, seed: int) -> dict:
    """seed 0: real prices; 1: shuffled prices (the confirmations must lose their effect there)."""
    if seed == 0:
        return job(asset)
    from signals.scoring.null import null_cache
    return job(asset, BASES, null_cache(asset, seed, lambda c: c))


def main() -> None:
    assets = [a for a in sys.argv[1:] if a in ASSETS] or list(ASSETS)
    jobs = [(a, s) for a in assets for s in (0, 1)]
    with ProcessPoolExecutor(max_workers=3) as pool:
        for (a, s), d in zip(jobs, pool.map(seeded, *zip(*jobs))):
            (OUT / f"turns_{a}_{s}.json").write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
            print(a, s, {b: len(r) for b, r in d.items()}, flush=True)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
