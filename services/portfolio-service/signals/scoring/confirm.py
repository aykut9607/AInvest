r"""Every rule on every timeframe (15m ... 1M) of every asset, at the tops and bottoms of that timeframe (Aykut, 25 Nov).

  .\venv\Scripts\python.exe -m signals.scoring.confirm          -> data/reports/confirm_<asset>_<seed>.json
  .\venv\Scripts\python.exe -m signals.scoring.confirm rescore  only the outcomes again (WORKED or ROOM changed)

Candidate: a pivot of the timeframe (5 bars before, 2 after; known two bars later). At each one: which rules were present ON THAT TIMEFRAME,
using only what was known when the pivot was known. Then the 15m candles: how far did price go before the pivot was exceeded (by more than
0.25 ATR)?
  worked   at least 2 % inside 40 bars (1w: 26, 1M: 12; Aykut: "2 % is a confirmation"); the average move of those is reported
  after    2 % again from the close at which the pivot was known
Rules are a tree: category -> rule -> variation ("Elliott|ABC|yassı (genişleyen)"). Elliott corrections count only after a finished 12345.
"""

from __future__ import annotations

import json
import sys
from bisect import bisect_left, bisect_right
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone

import numpy as np

from signals.data.candles import TIMEFRAMES
from signals.indicators.cvd import cvd
from signals.patterns import elliott as ew
from signals.patterns.fib import in_range, near
from signals.rules import elliott_check, pa_detect, smc_detect
from signals.scoring.null import NO_VOLUME
from signals.scoring.rule_events import SPAN, Context
from signals.scoring.run import OUT
from signals.scoring.turns import Path15, key_levels, load_full, make_levels, ts
from signals.structure.pivots import HIGH, LOW, pivot_highs, pivot_lows
from signals.structure.sfp import find_open_sfps
from signals.structure.zigzag import SwingPoint, zigzag

ASSETS = ("BTCUSDT", "XAU", "SPX")
LEFT, RIGHT = 5, 2
ROOM = 0.0             # x ATR: Aykut, 26 Nov: the top may not be taken at all ("2. mumdaki tepeyi almaması")
# "Worked" (Aykut, 26 Nov): from the top, at least this many % before the top is taken, within the window below. LTF (15m-2h): BTC 2 %, gold and
# the S&P 1.5 %. HTF (4h and up): 4 % (BTC) and 3 % (gold, S&P) on 4h, and on the higher frames the move a top reaches as often as a 4h top
# reaches that (first 70 % of the data, measured on 26 Nov): with a flat 4 % almost every daily BTC top "worked" (96 %), so no rule stood out.
LTF_FRAMES = ("15m", "30m", "45m", "1h", "2h")
NEED_LTF = {"BTCUSDT": 2.0, "XAU": 1.5, "SPX": 1.5}
NEED_HTF = {"BTCUSDT": {"4h": 4.0, "6h": 5.0, "12h": 7.0, "1d": 10.0, "3d": 20.0, "1w": 27.0, "1M": 60.0},
            "XAU": {"4h": 3.0, "6h": 4.0, "12h": 5.0, "1d": 8.0, "3d": 15.0, "1w": 18.0, "1M": 30.0},
            "SPX": {"4h": 3.0, "6h": 4.0, "12h": 5.5, "1d": 8.0, "3d": 14.0, "1w": 18.0, "1M": 40.0}}


def need(asset: str, f: str) -> float:
    return NEED_LTF[asset] if f in LTF_FRAMES else NEED_HTF[asset][f]


WORKED = {a: {f: need(a, f) for f in TIMEFRAMES} for a in ASSETS}
WINDOWS = {"1w": 26, "1M": 12}          # bars the move may take (40 on the other frames): later moves are not this top's doing


def bars_of(f: str) -> int:
    return WINDOWS.get(f, 40)


def outcome(path, begin: float, known: float, window: float, price: float, entry: float, side: int, room: float, worked: float) -> tuple:
    """(move %, worked, worked after the pivot was known, that move %)."""
    move = 100 * path.reaction(begin, begin + window, price, side, room) / price
    later = 100 * (path.reaction(known, known + window, price, side, room) - abs(price - entry)) / entry
    return round(move, 3), bool(move >= worked), bool(later >= worked), round(max(0.0, later), 3)


DEGREES = (1.5, 2.0, 3.0, 4.0)
CHILD = {"1M": "1w", "1w": "1d", "3d": "12h", "1d": "4h", "12h": "2h", "6h": "1h", "4h": "1h", "2h": "30m", "1h": "15m", "45m": "15m", "30m": "15m"}
BANDS = {"0,34–0,382": (0.33, 0.393), "0,5": (0.485, 0.515), "0,618–0,66": (0.60, 0.68), "0,709": (0.69, 0.73), "0,786": (0.763, 0.81), "0,886": (0.86, 0.912)}
TARGETS = (1.0, 1.272, 1.618, 1.79, 2.0, 2.618, 2.79, 3.0, 3.618, 3.79, 4.0, 4.618)          # Aykut's trend fib
# Aykut's table (25 Nov): XB, AC, BD, XD. Cypher: C beyond A (AC of AB), D = 0.786 of X-C
HARMONIC = {"Bat": ((0.382, 0.5), (0.382, 0.886), (1.618, 2.618), (0.886, 0.886)), "Gartley": ((0.618, 0.618), (0.382, 0.886), (1.272, 1.618), (0.786, 0.786)),
            "Crab": ((0.382, 0.618), (0.382, 0.886), (2.24, 3.618), (1.618, 1.618)), "Deep Crab": ((0.886, 0.886), (0.382, 0.886), (2.618, 3.618), (1.618, 1.618)),
            "Butterfly": ((0.786, 0.786), (0.382, 0.886), (1.618, 2.618), (1.272, 1.618)), "Cypher": ((0.382, 0.618), (1.414, 2.14), (1.272, 2.0), (0.786, 0.786))}


# ---------- Elliott: a tree

def three_legs(p) -> str | None:
    """A corrective S-A-B-C: its name, or None."""
    a = abs(p[1].price - p[0].price)
    if a <= 0:
        return None
    s = 1 if p[1].price > p[0].price else -1
    rb, rc = abs(p[2].price - p[1].price) / a, abs(p[3].price - p[2].price) / a
    beyond = s * p[3].price > s * p[1].price
    if rb < 0.9:
        return "zigzag" if beyond and 0.5 <= rc <= 2.8 else None
    if rb <= 1.4:
        if rb <= 1.05 and abs(p[3].price - p[1].price) <= 0.15 * a:
            return "yassı (normal)"
        if beyond and rc <= 2.8:
            return "yassı (genişleyen)"
        if rb > 1.0 and not beyond and rc >= 0.5:
            return "yassı (kaçan)"
    return None


def five_waves(p) -> str | None:
    c = ew._impulse(tuple(p))
    if c is None:
        return None
    if c.kind == ew.DIAGONAL:
        return "diyagonal"
    s = 1 if p[1].kind == HIGH else -1
    if s * p[5].price <= s * p[3].price:
        return "güdük 5"
    return {ew.EXT_1ST: "1. dalga uzayan", ew.EXT_3RD: "3. dalga uzayan", ew.EXT_5TH: "5. dalga uzayan"}.get(c.extension, "uzamasız")


def elliott(points: list[SwingPoint], ended: dict[int, int] | None = None, known: int = 10**9) -> set[str]:
    """What the last point ends. Corrections need a finished 12345 at their start ("12345 olmadan ABC olmaz"); `ended`: bars at which a
    12345 of any degree ended -> bar at which that was known (a correction is often counted one degree smaller than the impulse)."""
    out: set[str] = set()
    n = len(points)
    if n >= 6:
        k = five_waves(points[-6:])
        if k:
            out.add(f"12345 sonu|{k}")
    if n >= 5:
        p0, p1, p2, p3, p4 = points[-5:]
        s = 1 if p1.kind == HIGH else -1
        if s * p2.price > s * p0.price and s * p3.price > s * p1.price and s * p4.price > s * p1.price:
            out.add("4. dalga sonu|1'in alanına girmeden")

    if n >= 3:          # wave 2 of a new move: the next leg would be wave 3 (E-01, E-10: deeper than 0.382, never beyond the start)
        p0, p1, p2 = points[-3:]
        back = abs(p2.price - p1.price) / max(abs(p1.price - p0.price), 1e-12)
        if 0.382 <= back <= 0.886:
            start = (ended or {}).get(p0.index, 10**10) <= known          # a 12345 of the other direction ended where this move began
            out.add("2. dalga sonu|" + ("önceki 12345'in bittiği yerden" if start else "başlangıcı belirsiz"))

    def after_impulse(legs: int) -> bool:
        i = n - 1 - legs                                                  # index of the point the correction starts from
        if i < 0:
            return False
        return (ended or {}).get(points[i].index, 10**10) <= known or (i >= 5 and five_waves(points[i - 5:i + 1]) is not None)

    def legs3(i: int) -> str | None:
        return three_legs(points[i:i + 4])

    if after_impulse(2):
        out.add("B sonu|12345'ten sonra")
    if after_impulse(3):
        k = legs3(n - 4)
        if k:
            out.add(f"ABC sonu|{k}")
    if after_impulse(5) and elliott_check.check_triangle([p.price for p in points[-6:]], [p.index for p in points[-6:]]).possible:
        out.add("ABCDE üçgen sonu|12345'ten sonra")
    if after_impulse(4) and legs3(n - 5):
        out.add("X sonu|tek bacak X")
    if after_impulse(6) and legs3(n - 7) and legs3(n - 4):
        out.add("X sonu|ABC X")
    if after_impulse(7) and legs3(n - 8) and legs3(n - 4):
        out.add("WXY sonu|tek bacak X")
    if after_impulse(9) and legs3(n - 10) and legs3(n - 7) and legs3(n - 4):
        out.add("WXY sonu|ABC X")
    if after_impulse(11) and legs3(n - 12) and legs3(n - 8) and legs3(n - 4):
        out.add("WXYXZ sonu|tek bacak X")
    if after_impulse(15) and all(legs3(n - 16 + 3 * j) for j in range(5)):
        out.add("WXYXZ sonu|ABC X")
    return out


def harmonics(points: list[SwingPoint]) -> set[str]:
    out: set[str] = set()
    if len(points) >= 5:
        x, a, b, c, d = points[-5:]
        s = 1 if a.price > x.price else -1
        v = [s * q.price for q in (x, a, b, c, d)]
        xa, ab, bc, cd = v[1] - v[0], v[1] - v[2], v[3] - v[2], v[3] - v[4]
        if min(xa, ab, bc, cd) > 0:
            for name, (xb, ac, bd, xd) in HARMONIC.items():
                if not (in_range(ab / xa, *xb) and in_range(bc / ab, *ac) and in_range(cd / bc, *bd)):
                    continue
                far = (v[3] - v[4]) / (v[3] - v[0]) if name == "Cypher" else (v[1] - v[4]) / xa
                if in_range(far, *xd) and (name == "Cypher" or ab / xa < 1):
                    out.add(name)
    if len(points) >= 4:
        a, b, c, d = points[-4:]
        ab, bc, cd = abs(b.price - a.price), abs(c.price - b.price), abs(d.price - c.price)
        if ab and 0.382 <= bc / ab <= 0.886 and near(cd / ab, 1.0):
            out.add("AB=CD")
    return out


# ---------- one timeframe

class Frame:
    def __init__(self, asset: str, f: str, cache: dict, shared: dict):
        self.asset, self.f, self.x = asset, f, Context(asset, f, cache)
        x = self.x
        self.span = SPAN[f].total_seconds()
        self.t = np.array([ts(c) for c in x.times])
        self.path = shared["path"]
        self.volume = asset not in NO_VOLUME
        self.rsi = np.array([np.nan if v is None else v for v in x.rsi])
        self.cvd = np.array([np.nan if v is None else v for v in cvd(x.candles)]) if asset == "BTCUSDT" else None
        self.deg = {m: zigzag(x.candles, multiple=m) for m in DEGREES}
        self.deg_known = {m: [p.confirmed_at for p in v] for m, v in self.deg.items()}
        self.ended: dict[int, int] = {}
        self.impulse: dict[int, list[SwingPoint]] = {}          # end bar -> its 0..5 (for the pictures)
        for v in self.deg.values():
            for i in range(5, len(v)):
                if five_waves(v[i - 5:i + 1]):
                    self.ended[v[i].index] = min(self.ended.get(v[i].index, 10**9), v[i].confirmed_at)
                    self.impulse[v[i].index] = v[i - 5:i + 1]
        kid = Context(asset, CHILD[f], cache) if f in CHILD and len(cache.get((asset, CHILD[f]), ())) > 60 else None
        self.child = np.array([ts(kid.times[p.index]) for p in zigzag(kid.candles, multiple=2.0)]) if kid else None
        self.sfp: dict[int, list] = {1: [], -1: []}
        for s in find_open_sfps(x.candles):
            self.sfp[1 if s.direction == "bullish" else -1].append((s.sweep_index, s.confirmed_at, s.pivot_index, s.extreme))
        self.candle: dict[int, set] = {}
        for i, n, d in smc_detect.candle_patterns(x.candles):
            if d and n in (smc_detect.PIN, smc_detect.ENGULFING):
                self.candle.setdefault(i, set()).add((n, 1 if d == "up" else -1))
        self.lines = [(line, line.touches[-1].confirmed_at, line.break_index if line.break_index is not None else 10**9, 1 if line.direction == "up" else -1)
                      for line in pa_detect.trend_lines(x.candles, x.swings)]
        self.levels = dict(shared["levels"])
        self.own_levels()

    def own_levels(self):
        x = self.x
        def add(name, rows):
            if rows:
                self.levels[name] = make_levels(rows, self.path)
        rows = []
        for ps, side in ((pivot_lows([c.low for c in x.candles]), -1), (pivot_highs([c.high for c in x.candles]), 1)):
            for p in ps:                                                  # support that was lost = resistance (S/R flip)
                seg = x.bars.close[p.confirmed_at + 1:p.confirmed_at + 400]
                m = seg < p.value if side == -1 else seg > p.value
                if m.any():
                    rows.append((ts(x.known(p.confirmed_at + 1 + int(m.argmax()))), p.value, side, None))
        add("Price action|S/R flip|kaybedilen destek / kırılan direnç", rows)
        for name, zones in (("order block", smc_detect.order_blocks(x.candles, x.swings)), ("FVG", smc_detect.fair_value_gaps(x.candles, 0.25)),
                            ("arz/talep", smc_detect.supply_demand(x.candles)), ("breaker", smc_detect.breakers(x.candles, x.swings))):
            add(f"Smart money|{name}|ilk dokunuş", [(ts(x.known(z.known_at)), z.high if z.direction == "up" else z.low, 1 if z.direction == "up" else -1, None) for z in zones])
        rows = []
        for r in smc_detect.ranges(x.swings) + smc_detect.ranges(x.small):
            k = ts(x.known(r.known_at))
            rows += [(k, r.high, -1, k + 120 * self.span), (k, r.low, 1, k + 120 * self.span)]
        if rows:
            self.levels["Price action|range|uç"] = make_levels(rows, self.path, True)

    def points(self, m: float, j: int, price: float, kind: str, known: int) -> list[SwingPoint]:
        """Confirmed swings of one degree before bar j, the running opposite extreme if needed, and bar j itself as the last point."""
        n = bisect_left(self.deg_known[m], j)
        pts, b = self.deg[m][max(0, n - 22):n], self.x.bars
        if not pts:
            return []
        if pts[-1].kind == kind:
            a = pts[-1].index + 1
            if a >= j:
                return []
            k = a + int(b.low[a:j].argmin() if kind == HIGH else b.high[a:j].argmax())
            q = float(b.low[k] if kind == HIGH else b.high[k])
            if abs(q - price) < b.atr[j - 1]:
                return []
            pts = pts + [SwingPoint(LOW if kind == HIGH else HIGH, k, q, j)]
        i = pts[-1].index
        if i >= j or ((price <= pts[-1].price) if kind == HIGH else (price >= pts[-1].price)):
            return []
        further = b.high[i + 1:j].max(initial=-np.inf) > price if kind == HIGH else b.low[i + 1:j].min(initial=np.inf) < price
        return [] if further else pts + [SwingPoint(kind, j, price, j)]

    def inner(self, pts: list[SwingPoint]) -> bool:
        """5-3-5-3-5 / 5-3-5 inside, counted on the child frame: motive legs need at least 5 inner swings, corrective legs 3."""
        if self.child is None:
            return False
        for k, (a, z) in enumerate(zip(pts, pts[1:])):
            inside = bisect_right(self.child, self.t[z.index]) - bisect_left(self.child, self.t[a.index])
            if inside + 1 < (5 if k % 2 == 0 else 3):
                return False
        return True

    def reshort(self, j: int, price: float, side: int) -> dict[str, float]:
        """Retracement of the leg that made the low (Aykut): low = the lowest since price was last at this height; high = the most recent
        swing high before that low which price has not exceeded yet. Mirror for a relong. -> {degree: ratio}"""
        b = self.x.bars
        a = max(0, j - 600)
        over = np.nonzero(b.high[a:j] >= price)[0] if side == -1 else np.nonzero(b.low[a:j] <= price)[0]
        start = a + int(over[-1]) + 1 if len(over) else a
        if start >= j - 1:
            return {}
        k = start + int(b.low[start:j].argmin() if side == -1 else b.high[start:j].argmax())
        end = float(b.low[k] if side == -1 else b.high[k])
        out = {}
        for m in DEGREES:
            n = bisect_left(self.deg_known[m], j)
            for p in reversed(self.deg[m][max(0, n - 40):n]):
                if p.index < k and p.kind == (HIGH if side == -1 else LOW) and ((p.price > price) if side == -1 else (p.price < price)):
                    if abs(p.price - end) >= 3 * b.atr[j - 1]:
                        out[m] = (price - end) / (p.price - end)
                    break
        return out

    def at(self, j: int, conf: int, price: float, side: int) -> set[str]:
        return self.momentum(j, side) | self.structure(j, conf, price, side, self.t[j] + self.span)

    def momentum(self, j: int, side: int) -> set[str]:
        """Divergences at the top itself (bar j closed). The indicator's own label is not used: it needs 5 later bars."""
        b, out = self.x.bars, set()
        atr, hi = b.atr[j - 1], (b.high if side == -1 else -b.low)
        a = max(0, j - 60)
        if j - a > 6:
            r = self.rsi * (1 if side == -1 else -1)
            seg = r[a:j - 1]
            if not np.isnan(seg).all():
                u = a + int(np.nanargmax(seg))
                if hi[j] > hi[u] and r[j] < r[u] - 0.5 and hi[u] >= hi[a:u + 1].max() - atr:
                    out.add("Uyumsuzluk|RSI|tepede anlık")
            u = a + int(hi[a:j - 2].argmax())                             # the previous price high of the last 60 bars
            for name, v in (("CVD", self.cvd), ("hacim", b.volume if self.volume else None)):
                if v is None or np.isnan(v[j]) or np.isnan(v[u]) or not hi[j] > hi[u] or j - u < 3:
                    continue
                lower = (v[j] < v[u] if side == -1 else v[j] > v[u]) if name == "CVD" else v[j] < v[u]
                if lower:
                    out.add(f"Uyumsuzluk|{name}|tepede anlık")
            if hi[j] < hi[u] and r[j] > r[u] + 0.5 and j - u >= 5:
                out.add("Uyumsuzluk|Trend Devam (gizli)|tepede anlık")
        return out

    def structure(self, j: int, conf: int, price: float, side: int, when: float, near: float | None = None, skip: frozenset = frozenset()) -> set[str]:
        """Everything that is not momentum; reads nothing of bars after `conf`, and of bar j only `price`. `near`: the most that counts as
        "at the level" (default 0.3 ATR of the frame); levels named in `skip` are not looked at."""
        x, b, out = self.x, self.x.bars, set()
        atr, kind = b.atr[j - 1], HIGH if side == -1 else LOW
        tol = 0.3 * atr if near is None else min(near, 0.3 * atr)
        # --- SFP
        for sweep, done, pivot, extreme in self.sfp[side][bisect_left(self.sfp[side], (j - 1,)):]:
            if sweep > j:
                break
            if done <= conf and abs(extreme - price) <= 0.05 * atr:
                weak = (self.rsi[sweep] - self.rsi[pivot]) * side > 0
                thin = self.volume and b.volume[sweep] < b.volume[pivot]
                out.add("SFP|" + ("RSI ve hacim uyumsuz" if weak and thin else "RSI uyumsuz" if weak else "hacim uyumsuz" if thin else "uyumsuzluk yok") + "|")
        # --- Elliott, harmonic, wedge
        for m in DEGREES:
            pts = self.points(m, j, price, kind, conf)
            if len(pts) < 4:
                continue
            for n in elliott(pts, self.ended, conf):
                out.add(f"Elliott|{n}")
                if n.startswith("12345") and self.inner(pts[-6:]):
                    out.add("Elliott|12345 sonu|iç yapı 5-3-5-3-5 tutuyor")
                if n.startswith("ABC sonu") and self.inner(pts[-4:]):
                    out.add("Elliott|ABC sonu|iç yapı 5-3-5 tutuyor")
            for n in harmonics(pts):
                out.add(f"Harmonik|{n}|")
            if len(pts) >= 5:
                shift = max(0, pts[-5].index - 1)
                run = [SwingPoint(p.kind, p.index - shift, p.price, j - shift) for p in pts[-5:]]
                for pat in pa_detect.converging_patterns(x.candles[shift:j + 1], run):
                    if pat.kind == pa_detect.SYMMETRIC or (pat.kind == pa_detect.RISING_WEDGE) == (side == -1):
                        out.add(f"Price action|{pat.kind}|ucunda")
            # --- trend fib target reached
            if len(pts) >= 4:
                p0, p1, p2 = pts[-4], pts[-3], pts[-2]
                s = -side
                if s * p2.price > s * p0.price and s * (p1.price - p0.price) > 0:
                    e = (price - p2.price) / (p1.price - p0.price)
                    for k in TARGETS:
                        if abs(e - k) <= 0.03:
                            out.add(f"Fibonacci|trend fib hedefi|{str(k).replace('.', ',')}")
        for r in self.reshort(j, price, side).values():
            for n, (lo, hi_) in BANDS.items():
                if lo <= r <= hi_:
                    out.add(f"Fibonacci|reshort / relong|{n}")
        # --- candles, trend lines, levels
        for i in range(j, min(j + 1, conf) + 1):
            for n, d in self.candle.get(i, ()):
                if d == side:
                    out.add(f"Price action|mum|{n}")
        if any(d == side and k < j <= e and j - line.touches[-1].index < 300 and abs(line.at(j) - price) <= tol for line, k, e, d in self.lines):
            out.add("Price action|trend çizgisi|yeni temas")
        for name, lv in self.levels.items():
            if name not in skip and lv.hit(side, when, price, tol):
                out.add(name)
        return out


def shared_levels(asset: str, cache: dict) -> dict:
    """Levels that do not depend on the timeframe looked at."""
    path, out = Path15(cache[(asset, "15m")]), {}
    for kind, name in (("D", "günlük"), ("W", "haftalık"), ("M", "aylık"), ("3M", "3 aylık"), ("6M", "6 aylık"), ("Y", "yıllık")):
        rows = [(ts(t), p, s, None) for t, p, s in key_levels(cache[(asset, "1d")], kind)]
        if rows:
            out[f"Key level|{name}|test edilmemiş"] = make_levels(rows, path)
    x = Context(asset, "15m", cache)
    for kind, name, days in (("d", "önceki gün", 1), ("w", "önceki hafta", 7), ("m", "önceki ay", 31)):
        rows, naked = {}, []
        for a, z, v in x.profiles(kind):
            i = x.last_closed(z)
            if i < 0:
                continue
            for n, p in v.items():
                rows.setdefault(n, []).append((ts(z), p, 1 if x.candles[i].close > p else -1, ts(z) + days * 86400))
            if "POC" in v:
                k, p = ts(z) + days * 86400, v["POC"]
                lo, hi = int(np.searchsorted(path.t, ts(z))), int(np.searchsorted(path.t, k))
                q = x.last_closed(datetime.fromtimestamp(k, timezone.utc))
                if hi > lo and not ((path.low[lo:hi] <= p) & (path.high[lo:hi] >= p)).any():
                    naked.append((k, p, 1 if x.candles[q].close > p else -1, None))
        for n, r in rows.items():
            out[f"{'Hacim profili' if n in ('VAH', 'POC', 'VAL', 'VWAP') else 'Önceki dönem'}|{name} {n}|"] = make_levels(r, path, True)
        if naked:
            out[f"Hacim profili|nPOC {name.split()[1]}|dokunulmamış"] = make_levels(naked, path)
    for name in ("Pazartesi", "Hafta", "Ay"):
        rows = []
        for r in x.ranges(name):
            size = r.high - r.low
            rows += [(ts(r.known), r.high + 0.164 * size, -1, ts(r.until)), (ts(r.known), r.low - 0.164 * size, 1, ts(r.until))]
        out[f"EXT bandı|{name}|1,114–1,214"] = make_levels(rows, path)
    return {"path": path, "levels": out}


def job(asset: str, f: str, seed: int) -> list:
    if seed == 0:
        cache = load_full(asset)
    else:
        from signals.scoring.null import null_cache
        cache = null_cache(asset, seed, lambda c: c)
    if len(cache[(asset, f)]) < 80:
        return []
    shared = shared_levels(asset, cache)
    fr = Frame(asset, f, cache, shared)
    x, b, path, rows = fr.x, fr.x.bars, shared["path"], []
    funding = ([], [])
    if asset == "BTCUSDT" and seed == 0:
        from signals.data import derivatives
        r = derivatives.load("funding")
        funding = ([ts(a) for a, _ in r], [v for _, v in r])
    window = bars_of(f) * fr.span
    for ps, side in ((pivot_highs([c.high for c in x.candles], LEFT, RIGHT), -1), (pivot_lows([c.low for c in x.candles], LEFT, RIGHT), 1)):
        for p in ps:
            j, conf = p.index, p.confirmed_at
            atr = b.atr[j - 1] if j else np.nan
            if np.isnan(atr) or j < (24 if f == "1M" else 70) or conf >= len(x.candles):
                continue
            begin, known = fr.t[j] + fr.span, fr.t[conf] + fr.span
            if begin + window > path.t[-1]:
                continue
            got = outcome(path, begin, known, window, p.value, b.close[conf], side, ROOM * atr, need(asset, f))
            tags = fr.at(j, conf, p.value, side)
            i = bisect_right(funding[0], fr.t[j]) - 1
            if i >= 0 and fr.t[j] - funding[0][i] < 9 * 3600 and -side * funding[1][i] >= 0.0005:
                tags.add("Funding|aşırı|±%0,05")
            rows.append([float(fr.t[j]), side, *(v.item() if hasattr(v, "item") else v for v in got), sorted(tags), round(p.value, 2)])
    return sorted(rows)


def rescore(asset: str, seed: int) -> dict:
    """The stored candidates (their confirmations do not change) with a new outcome: for a changed WORKED or ROOM."""
    if seed == 0:
        cache = load_full(asset)
    else:
        from signals.scoring.null import null_cache
        cache = null_cache(asset, seed, lambda c: c)
    path = Path15(cache[(asset, "15m")])
    old = json.loads((OUT / f"confirm_{asset}_{seed}.json").read_text(encoding="utf-8"))
    for f, rows in old.items():
        x, span, new = Context(asset, f, cache), SPAN[f].total_seconds(), []
        b, at = x.bars, {ts(c): i for i, c in enumerate(x.times)}
        for r in rows:
            j = at[r[0]]
            conf, side = j + RIGHT, r[1]
            price = float(b.high[j] if side == -1 else b.low[j])
            got = outcome(path, r[0] + span, ts(x.times[conf]) + span, bars_of(f) * span, price, float(b.close[conf]), side, ROOM * b.atr[j - 1], need(asset, f))
            r[6] = [g for g in r[6] if not g.endswith("|gösterge etiketi")]          # needed bars after the candidate was known (25 Nov)
            new.append([r[0], side, *(v.item() if hasattr(v, 'item') else v for v in got), r[6], r[7]])
        old[f] = new
    (OUT / f"confirm_{asset}_{seed}.json").write_text(json.dumps(old, ensure_ascii=False), encoding="utf-8")
    return {f: len(v) for f, v in old.items()}


def main() -> None:
    if "rescore" in sys.argv:
        jobs = [(a, s) for a in ASSETS for s in (0, 1)]
        with ProcessPoolExecutor(max_workers=3) as pool:
            for j, n in zip(jobs, pool.map(rescore, *zip(*jobs))):
                print(*j, n, flush=True)
        return
    assets = [a for a in sys.argv[1:] if a in ASSETS] or list(ASSETS)
    frames = [f for f in sys.argv[1:] if f in TIMEFRAMES] or TIMEFRAMES
    jobs = [(a, f, s) for a in assets for s in (0, 1) for f in frames]
    out: dict = {}
    with ProcessPoolExecutor(max_workers=4) as pool:
        for (a, f, s), rows in zip(jobs, pool.map(job, *zip(*jobs))):
            out.setdefault((a, s), {})[f] = rows
            print(a, f, s, len(rows), flush=True)
    for (a, s), d in out.items():
        path = OUT / f"confirm_{a}_{s}.json"
        d = {**(json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}), **d}
        path.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
