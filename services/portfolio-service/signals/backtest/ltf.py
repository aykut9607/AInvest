"""LTF confirmation index: every 1h SFP and regular RSI / CVD divergence, searchable by time (RULES.md 3).

A long needs a bullish signal (bullish SFP, P.U), a short a bearish one (bearish SFP, N.U). The time of a signal is the
close of the bar it is confirmed at, so only signals already known inside the window count.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from datetime import datetime, timedelta

from signals.backtest.engine import LONG
from signals.data.candles import Candle
from signals.indicators.cvd import cvd_divergences
from signals.indicators.rsi_divergence import REGULAR_BEARISH, REGULAR_BULLISH, rsi_divergences
from signals.structure.sfp import BULLISH, find_sfps


class LtfSignals:
    def __init__(self, candles: Sequence[Candle], bar_span: timedelta = timedelta(hours=1)):
        bull, bear = [], []
        known = lambda index: candles[index].time + bar_span        # signal known at the close of its bar
        for s in find_sfps(candles):
            (bull if s.direction == BULLISH else bear).append(known(s.confirmed_at))
        for d in rsi_divergences(candles) + cvd_divergences(candles):
            if d.kind == REGULAR_BULLISH:
                bull.append(known(d.confirmed_at))
            elif d.kind == REGULAR_BEARISH:
                bear.append(known(d.confirmed_at))
        self._bull, self._bear = sorted(bull), sorted(bear)
        self.first = candles[0].time if candles else None
        self.last = candles[-1].time if candles else None

    def covers(self, start: datetime, end: datetime) -> bool:
        """True when 1h data exists for the whole window (gold/S&P 1h only reaches back ~2 years)."""
        return self.first is not None and self.first <= start and end <= self.last + timedelta(hours=1)

    def __call__(self, start: datetime, end: datetime, direction: str) -> bool:
        times = self._bull if direction == LONG else self._bear
        return bisect_right(times, end) > bisect_left(times, start)
