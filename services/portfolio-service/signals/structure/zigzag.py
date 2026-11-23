"""ATR ZigZag: alternating tops and bottoms for Elliott waves, harmonic XABCD points and Fibonacci legs.

A top is accepted once price has come down from the highest high since the last bottom by `multiple x ATR(14)`
(measured at the bar where that happens); a bottom the mirror way. So tops and bottoms always alternate, small
wiggles inside the threshold are ignored, and the threshold adapts to each market's volatility (BTC vs gold).
A larger multiple gives the main (HTF) structure, a smaller one the sub-waves (RULES.md 2).

Every point carries the bar it happened at and the bar it was confirmed at (no look-ahead in a replay).
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from signals.data.candles import Candle
from signals.structure.pivots import HIGH, LOW


@dataclass(frozen=True)
class SwingPoint:
    kind: str            # HIGH (top) or LOW (bottom)
    index: int           # bar of the extreme
    price: float         # its high (top) or low (bottom)
    confirmed_at: int    # bar at which the reversal reached the threshold


def wilder_atr(candles: Sequence[Candle], length: int = 14) -> list[float | None]:
    """Average True Range with Wilder's smoothing (TradingView ta.atr): None until `length` bars are known."""
    atr: list[float | None] = []
    true_ranges: list[float] = []
    previous_close = None
    current = None
    for candle in candles:
        true_range = candle.high - candle.low if previous_close is None else max(
            candle.high - candle.low, abs(candle.high - previous_close), abs(candle.low - previous_close))
        previous_close = candle.close
        true_ranges.append(true_range)
        if current is None:
            if len(true_ranges) == length:
                current = sum(true_ranges) / length          # seed: simple average of the first `length`
        else:
            current = (current * (length - 1) + true_range) / length
        atr.append(current)
    return atr


def zigzag(candles: Sequence[Candle], multiple: float = 3.0, atr_length: int = 14) -> list[SwingPoint]:
    """Confirmed alternating swing points, oldest first. The last, still-running extreme is not included."""
    atr = wilder_atr(candles, atr_length)
    points: list[SwingPoint] = []
    direction = None                 # HIGH: looking for a top (price rising), LOW: looking for a bottom
    high_i = low_i = None            # running extremes while the direction is unknown / since the last point

    for i, candle in enumerate(candles):
        if atr[i] is None:
            continue
        threshold = multiple * atr[i]
        if high_i is None:
            high_i = low_i = i
            continue
        if candle.high > candles[high_i].high:
            high_i = i
        if candle.low < candles[low_i].low:
            low_i = i

        if direction is None:
            # the first move larger than the threshold decides which way the structure starts
            if candles[high_i].high - candle.low >= threshold and high_i < i:
                points.append(SwingPoint(HIGH, high_i, candles[high_i].high, i))
                direction, low_i = LOW, i
            elif candle.high - candles[low_i].low >= threshold and low_i < i:
                points.append(SwingPoint(LOW, low_i, candles[low_i].low, i))
                direction, high_i = HIGH, i
        elif direction == HIGH:
            if candles[high_i].high - candle.low >= threshold and high_i < i:
                points.append(SwingPoint(HIGH, high_i, candles[high_i].high, i))
                direction, low_i = LOW, i
        else:
            if candle.high - candles[low_i].low >= threshold and low_i < i:
                points.append(SwingPoint(LOW, low_i, candles[low_i].low, i))
                direction, high_i = HIGH, i
    return points
