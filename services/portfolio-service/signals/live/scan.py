"""The moment a 15m / 30m / 45m / 1h divergence appears: which rules are present on each of the 12 timeframes, using only what is known then.

Trigger (Aykut, 25 Nov): at every 15m close the frames whose bar closed at that moment are searched in the order 15m, 30m, 45m, 1h. A bar that
is a new extreme while RSI, CVD or volume does not confirm it starts the scan; nothing found means waiting for the next close.
The scan looks for every rule on 15m ... 1M. Bars of the higher frames are usually still forming: their RSI and CVD are computed up to the
trigger, their volume is not used, and nothing after the trigger is read.
"""

from __future__ import annotations

from dataclasses import dataclass

from bisect import bisect_left

import numpy as np

from signals.data.candles import TIMEFRAMES
from signals.live import fibs
from signals.scoring.confirm import Frame, shared_levels

TRIGGER_FRAMES = ("15m", "30m", "45m", "1h")
TRIGGERS = ("Uyumsuzluk|RSI|tepede anlık", "Uyumsuzluk|CVD|tepede anlık", "Uyumsuzluk|hacim|tepede anlık")
LOOKBACK = 20          # bars of its own frame the trigger bar must be the extreme of
BASE = 900.0           # seconds of a 15m bar
NEAR = 0.3             # x ATR: distance that counts as "at the level"; the ATR is never larger than that of NEAR_FRAME
NEAR_FRAME = "4h"
MIN_BARS = {"1w": 40, "1M": 30}

# levels that belong to a calendar period, not to a chart: counted once, on the timeframe of their period
PERIOD_FRAME = (("yıllık", "1M"), ("3 aylık", "1M"), ("6 aylık", "1M"), ("aylık", "1M"), ("önceki ay", "1M"), ("nPOC ay", "1M"), ("|Ay|", "1M"),
                ("haftalık", "1w"), ("önceki hafta", "1w"), ("nPOC hafta", "1w"), ("|Hafta|", "1w"), ("", "1d"))


def period_frame(name: str) -> str:
    return next(f for word, f in PERIOD_FRAME if word in name)


@dataclass(frozen=True)
class Event:
    time: float                    # close of the trigger bar (UTC seconds)
    side: int                      # -1: top, short; +1: bottom, long
    frame: str                     # trigger frame
    reasons: tuple[str, ...]       # its divergences
    entry: float
    extreme: float
    atr_1h: float
    tags: dict[str, list[str]]     # timeframe -> confirmations
    fib: fibs.Fib | None = None    # what the trade is managed with, drawn on the trigger frame


class LiveFrame(Frame):
    """A timeframe whose last bar may still be forming."""

    def __init__(self, asset: str, f: str, cache: dict, shared: dict):
        super().__init__(asset, f, cache, shared)
        c = self.x.bars.close
        d = np.diff(c, prepend=c[0])
        self.up, self.down = self._rma(np.maximum(d, 0)), self._rma(np.maximum(-d, 0))
        self.period_levels = frozenset(shared["levels"])
        self.aux_volume = self.aux_cvd = None          # volume from another market, see auxvol.py

    def momentum(self, j: int, side: int) -> set[str]:
        out = super().momentum(j, side)
        a = max(0, j - 60)
        if j - a > 6 and (self.aux_volume is not None or self.aux_cvd is not None):
            hi = self.x.bars.high if side == -1 else -self.x.bars.low
            u = a + int(hi[a:j - 2].argmax())
            if hi[j] > hi[u] and j - u >= 3:
                if self.aux_volume is not None and self.aux_volume[j] < self.aux_volume[u]:
                    out.add("Uyumsuzluk|hacim|tepede anlık")
                if self.aux_cvd is not None and (self.aux_cvd[j] - self.aux_cvd[u]) * side > 0:
                    out.add("Uyumsuzluk|CVD|tepede anlık")
        return out

    def structure(self, j: int, conf: int, price: float, side: int, when: float, near: float | None = None, skip: frozenset = frozenset()) -> set[str]:
        """With volume of another market an SFP can also be one "with RSI and volume against it"."""
        out = super().structure(j, conf, price, side, when, near, skip)
        if self.aux_volume is None or "SFP|RSI uyumsuz|" not in out:
            return out
        atr, v = self.x.bars.atr[j - 1], self.aux_volume
        for sweep, done, pivot, extreme in self.sfp[side][bisect_left(self.sfp[side], (j - 1,)):]:
            if sweep > j:
                break
            if done <= conf and abs(extreme - price) <= 0.05 * atr and (self.rsi[sweep] - self.rsi[pivot]) * side > 0 and v[sweep] < v[pivot]:
                return (out - {"SFP|RSI uyumsuz|"}) | {"SFP|RSI ve hacim uyumsuz|"}
        return out

    @staticmethod
    def _rma(v: np.ndarray, n: int = 14) -> np.ndarray:
        out = np.full(len(v), np.nan)
        if len(v) > n:
            out[n] = v[1:n + 1].mean()
            for i in range(n + 1, len(v)):
                out[i] = (out[i - 1] * (n - 1) + v[i]) / n
        return out

    def forming_rsi(self, j: int, close: float) -> float:
        change = close - self.x.bars.close[j - 1]
        u, d = (self.up[j - 1] * 13 + max(change, 0.0)) / 14, (self.down[j - 1] * 13 + max(-change, 0.0)) / 14
        return 100.0 if d == 0 else 100 - 100 / (1 + u / d)

    def forming_momentum(self, j: int, side: int, price: float, close: float, cvd_now: float | None) -> set[str]:
        """The same tests as Frame.momentum with bar j cut at the trigger (no volume: half a bar has half a bar's volume)."""
        b, out = self.x.bars, set()
        a = max(0, j - 60)
        if j - a <= 6:
            return out
        hi, s = (b.high if side == -1 else -b.low), (1 if side == -1 else -1)
        top, atr, r = price * s, b.atr[j - 1], self.rsi * s
        now = self.forming_rsi(j, close) * s
        seg = r[a:j - 1]
        if not np.isnan(seg).all():
            u = a + int(np.nanargmax(seg))
            if top > hi[u] and now < r[u] - 0.5 and hi[u] >= hi[a:u + 1].max() - atr:
                out.add("Uyumsuzluk|RSI|tepede anlık")
        u = a + int(hi[a:j - 2].argmax())
        if self.cvd is not None and cvd_now is not None and not np.isnan(self.cvd[u]) and top > hi[u] and j - u >= 3 and (cvd_now - self.cvd[u]) * s < 0:
            out.add("Uyumsuzluk|CVD|tepede anlık")
        if top < hi[u] and now > r[u] + 0.5 and j - u >= 5:
            out.add("Uyumsuzluk|Trend Devam (gizli)|tepede anlık")
        return out

    def closed_at(self, when: float) -> int | None:
        """Index of the bar that closed exactly at `when`."""
        j = int(np.searchsorted(self.t, when - self.span))
        return j if j < len(self.t) and self.t[j] == when - self.span else None


class Scanner:
    """All frames of one asset. `cache`: {(asset, timeframe): candles}; the last candle of each list may be forming."""

    def __init__(self, asset: str, cache: dict, extra=None, aux=None):
        self.asset, self.extra = asset, extra          # extra(time, side) -> {timeframe: tags} for data that is not a candle (funding)
        shared = shared_levels(asset, cache)
        self.frames = {f: LiveFrame(asset, f, cache, shared) for f in TIMEFRAMES if len(cache.get((asset, f), ())) >= MIN_BARS.get(f, 80)}
        if aux is not None:
            for fr in self.frames.values():
                fr.aux_volume, fr.aux_cvd = aux.of(fr.t, fr.span)
        self.base = self.frames["15m"]

    def trigger(self, when: float, side: int) -> tuple[str, int, tuple[str, ...]] | None:
        """(frame, bar, divergences) of the first trigger frame that shows one at this close."""
        for f in TRIGGER_FRAMES:
            fr = self.frames[f]
            j = fr.closed_at(when)
            b = fr.x.bars
            if j is None or j < 120 or np.isnan(b.atr[j - 1]):
                continue
            if side == -1 and b.high[j] < b.high[j - LOOKBACK:j].max() or side == 1 and b.low[j] > b.low[j - LOOKBACK:j].min():
                continue
            found = tuple(sorted(t for t in fr.momentum(j, side) if t in TRIGGERS))
            if found:
                return f, j, found
        return None

    def scan(self, i: int, side: int, found: tuple[str, int, tuple[str, ...]]) -> Event:
        """Every rule on every frame at the close of 15m bar i."""
        frame, bar, reasons = found
        b, opened = self.base.x.bars, float(self.base.t[i])
        when, close = opened + BASE, float(b.close[i])
        tb = self.frames[frame].x.bars
        price = float(tb.high[bar] if side == -1 else tb.low[bar])
        near = NEAR * self._atr(NEAR_FRAME, opened)
        tags: dict[str, set[str]] = {}
        for f, fr in self.frames.items():
            fb = fr.x.bars
            j = fr.closed_at(when)
            if j is not None:                                                  # this frame's bar closed together with the trigger
                if j < 30 or np.isnan(fb.atr[j - 1]):
                    continue
                got = fr.structure(j, j, price, side, when, near, fr.period_levels)
                far = price < fb.high[j] if side == -1 else price > fb.low[j]
                if not far:
                    got |= fr.momentum(j, side)
            else:
                j = int(np.searchsorted(fr.t, opened, side="right")) - 1
                if j < 30 or j >= len(fb.close) or np.isnan(fb.atr[j - 1]):
                    continue
                k = int(np.searchsorted(self.base.t, fr.t[j]))                 # 15m bars of the forming bar
                far = k <= i and (b.high[k:i + 1].max() > price if side == -1 else b.low[k:i + 1].min() < price)
                got = {g for g in fr.structure(j, j - 1, price, side, when, near, fr.period_levels) if not g.startswith("Price action|mum")}
                if not far:
                    cvd_now = float(fr.cvd[j - 1]) + float(self.base.cvd[i]) - float(self.base.cvd[k - 1]) if fr.cvd is not None and k > 0 else None
                    got |= fr.forming_momentum(j, side, price, close, cvd_now)
            if far:                                                            # the bar went further elsewhere: this is not its extreme
                got = {g for g in got if not g.startswith(("Elliott", "Harmonik", "SFP"))}
            tags[f] = got
        for name, lv in self.base.levels.items():
            if name in self.base.period_levels and lv.hit(side, when, price, near):
                tags.setdefault(period_frame(name), set()).add(name)
        tags.setdefault(frame, set()).update(reasons)
        for f, got in (self.extra(when, side) if self.extra else {}).items():
            tags.setdefault(f, set()).update(got)
        return Event(when, side, frame, reasons, close, price, self._atr("1h", opened), {f: sorted(tags[f]) for f in TIMEFRAMES if tags.get(f)},
                     fibs.draw(tb.high, tb.low, bar, side, float(tb.atr[bar - 1])))

    def _atr(self, f: str, opened: float) -> float:
        fr = self.frames[f]
        j = int(np.searchsorted(fr.t, opened, side="right")) - 1
        return float(fr.x.bars.atr[min(j, len(fr.x.bars.atr)) - 1])

    def events(self, start: int = 0):
        """(15m bar, event) of every trigger, oldest first."""
        for i in range(max(120, start), len(self.base.t)):
            when = float(self.base.t[i]) + BASE
            for side in (-1, 1):
                found = self.trigger(when, side)
                if found:
                    yield i, self.scan(i, side, found)
