# This Source Code Form is subject to the terms of the Mozilla Public License, v. 2.0.
# If a copy of the MPL was not distributed with this file, You can obtain one at https://mozilla.org/MPL/2.0/.
#
# Python port of "RSI Divergence" (TradingView, Pine Script v5), (c) SERS41, MPL-2.0.
# Ported for AInvest 4.4 (23 Nov 2026): same RSI, same pivot settings and the same four divergence conditions,
# so the labels match the indicator on TradingView. The same divergence logic is also run on CVD (cvd.py).
"""Regular and hidden RSI divergences, exactly as the SERS41 RSI indicator draws them (RULES.md 3).

Pine logic, line by line:
  osc      = ta.rsi(close, 14)                                  -> rsi()
  plFound  = ta.pivotlow(osc, lbL=5, lbR=5) exists              -> pivots on the OSCILLATOR, not on price
  _inRange = 5 <= ta.barssince(plFound[1]) <= 60                -> bars between the two oscillator pivots
  P.U      = low[lbR] <  low at previous osc pivot  and  osc[lbR] >  previous osc pivot value   (price LL, osc HL)
  hidden   = low[lbR] >  low at previous osc pivot  and  osc[lbR] <  previous osc pivot value   (price HL, osc LL)
  N.U      = high[lbR] > high at previous osc pivot and  osc[lbR] <  previous value              (price HH, osc LH)
  hidden   = high[lbR] < high at previous osc pivot and  osc[lbR] >  previous value              (price LH, osc HH)
A label belongs to the pivot bar but appears lbR bars later (confirmed_at), which is when a replay may use it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from signals.data.candles import Candle
from signals.structure.pivots import HIGH, LOW, Pivot, pivots

REGULAR_BULLISH = "P.U"              # pozitif uyumsuzluk
HIDDEN_BULLISH = "TREND_DEVAM_BULL"  # gizli boğa
REGULAR_BEARISH = "N.U"              # negatif uyumsuzluk
HIDDEN_BEARISH = "TREND_DEVAM_BEAR"  # gizli ayı


@dataclass(frozen=True)
class DivergenceSettings:
    rsi_length: int = 14
    lookback_left: int = 5
    lookback_right: int = 5
    range_lower: int = 5
    range_upper: int = 60


@dataclass(frozen=True)
class Divergence:
    kind: str              # one of the four constants above
    oscillator: str        # "RSI" or "CVD"
    pivot_index: int       # bar of the second (current) pivot
    previous_index: int    # bar of the first pivot
    confirmed_at: int      # pivot_index + lookback_right
    price: float           # low (bullish) / high (bearish) at pivot_index
    previous_price: float
    value: float           # oscillator at pivot_index
    previous_value: float


def rma(values: Sequence[float | None], length: int) -> list[float | None]:
    """ta.rma (Wilder's moving average): seeded with the simple average of the first `length` values."""
    out: list[float | None] = []
    seed: list[float] = []
    current = None
    for v in values:
        if v is None:
            out.append(current)
            continue
        if current is None:
            seed.append(v)
            if len(seed) == length:
                current = sum(seed) / length
        else:
            current = (current * (length - 1) + v) / length
        out.append(current)
    return out


def rsi(closes: Sequence[float], length: int = 14) -> list[float | None]:
    """ta.rsi: RMA of gains over RMA of losses; 100 when there are no losses, 0 when there are no gains."""
    changes: list[float | None] = [None] + [closes[i] - closes[i - 1] for i in range(1, len(closes))]
    ups = rma([None if c is None else max(c, 0.0) for c in changes], length)
    downs = rma([None if c is None else max(-c, 0.0) for c in changes], length)
    result: list[float | None] = []
    for up, down in zip(ups, downs):
        if up is None or down is None:
            result.append(None)
        elif down == 0:
            result.append(100.0)
        elif up == 0:
            result.append(0.0)
        else:
            result.append(100.0 - 100.0 / (1.0 + up / down))
    return result


def _divergences(candles: Sequence[Candle], osc: Sequence[float | None], osc_name: str,
                 kind: str, s: DivergenceSettings) -> list[Divergence]:
    found: list[Divergence] = []
    osc_pivots: list[Pivot] = pivots(osc, s.lookback_left, s.lookback_right, kind)
    for previous, current in zip(osc_pivots, osc_pivots[1:]):
        # ta.barssince(plFound[1]) at the current confirmation bar = bars since the bar AFTER the previous one
        bars_since = current.confirmed_at - (previous.confirmed_at + 1)
        if not (s.range_lower <= bars_since <= s.range_upper):
            continue
        if kind == LOW:
            price, previous_price = candles[current.index].low, candles[previous.index].low
            if price < previous_price and current.value > previous.value:
                label = REGULAR_BULLISH
            elif price > previous_price and current.value < previous.value:
                label = HIDDEN_BULLISH
            else:
                continue
        else:
            price, previous_price = candles[current.index].high, candles[previous.index].high
            if price > previous_price and current.value < previous.value:
                label = REGULAR_BEARISH
            elif price < previous_price and current.value > previous.value:
                label = HIDDEN_BEARISH
            else:
                continue
        found.append(Divergence(label, osc_name, current.index, previous.index, current.confirmed_at,
                                price, previous_price, current.value, previous.value))
    return found


def divergences(candles: Sequence[Candle], osc: Sequence[float | None], osc_name: str,
                settings: DivergenceSettings = DivergenceSettings()) -> list[Divergence]:
    """All four divergence kinds of an oscillator against price, ordered by the bar they are confirmed at."""
    both = _divergences(candles, osc, osc_name, LOW, settings) + _divergences(candles, osc, osc_name, HIGH, settings)
    return sorted(both, key=lambda d: d.confirmed_at)


def rsi_divergences(candles: Sequence[Candle], settings: DivergenceSettings = DivergenceSettings()) -> list[Divergence]:
    return divergences(candles, rsi([c.close for c in candles], settings.rsi_length), "RSI", settings)
