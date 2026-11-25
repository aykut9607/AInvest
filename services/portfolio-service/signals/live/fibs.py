"""The two fibs a virtual trade is managed with (Aykut, 25 November 2026).

Scalp fib: from the last low to the reaction high after it (mirrored for shorts), 0 = the low, 1 = the high. The ten ratios come from a published
plan (BTC, 13-14 November 2026): its ten prices solve to these three-decimal ratios with an error below 0.3 USD, anchors 67,460.3 -> 70,182.5.
Trend fib: the same leg measured from the extreme the trade was opened at (FIBONACCI.md: 2 + k x (1 - 0)). At a divergence point 2 may sweep
point 0, so FT-01 (point 2 may not pass point 0) is replaced by the stop of the scalp fib.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

STOP = -0.412
LIQUIDITY = (-0.112, -0.270)          # SFP zones below the low: the stop leaves room for them
REENTRY = (0.116, 0.212)              # RELONG / RESHORT
SCALP = (("SCALP_TP", 0.722), ("TP1", 0.902), ("TP2", 1.236), ("TP3", 1.618), ("MARKET_SELL", 1.952))
TREND = (("TREND_1.272", 1.272), ("TREND_2.618", 2.618), ("TREND_3.618", 3.618), ("TREND_4.618", 4.618), ("TREND_5.618", 5.618))

LOOK = 60                 # bars of the trigger timeframe in which the last low and the reaction are looked for
MIN_LEG = 2.0             # x ATR of that timeframe: a smaller reaction is noise, no fib can be drawn on it


@dataclass(frozen=True)
class Fib:
    side: int
    start: float              # 0: the last low (long) / high (short)
    end: float                # 1: the reaction after it
    extreme: float            # where the trigger bar turned
    redrawn: bool             # the reaction was too small or price went beyond the stop level: drawn from the new extreme

    @property
    def leg(self) -> float:
        return abs(self.end - self.start)

    def scalp(self, ratio: float) -> float:
        return self.start + self.side * ratio * self.leg

    def trend(self, ratio: float) -> float:
        return self.extreme + self.side * ratio * self.leg

    def as_dict(self) -> dict:
        r = lambda v: round(v, 2)
        return {"start": r(self.start), "end": r(self.end), "extreme": r(self.extreme), "redrawn": self.redrawn, "stop": r(self.scalp(STOP)),
                "liquidity": [r(self.scalp(x)) for x in LIQUIDITY], "reentry": [r(self.scalp(x)) for x in REENTRY],
                "scalp": {n: r(self.scalp(x)) for n, x in SCALP}, "trend": {n: r(self.trend(x)) for n, x in TREND}}


def draw(high: np.ndarray, low: np.ndarray, j: int, side: int, atr: float) -> Fib | None:
    """The fib known at the close of bar j (nothing after j is used); None when there is no leg to draw it on."""
    lo, hi = (low, high) if side == 1 else (-high, -low)
    a = max(0, j - LOOK)
    if j - a < 10 or not atr > 0:
        return None
    extreme = float(lo[j])
    u = a + int(lo[a:j - 2].argmin())
    start, end = float(lo[u]), float(hi[u + 1:j + 1].max())
    redrawn = end - start < MIN_LEG * atr or extreme < start + STOP * (end - start)
    if redrawn:
        start = min(extreme, start)
        if end - start < MIN_LEG * atr:
            end = float(hi[a:j + 1].max())
        if end - start < MIN_LEG * atr:
            return None
    return Fib(side, side * start, side * end, side * extreme, redrawn)
