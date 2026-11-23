"""Event backtest of one setup: wait for the zone, enter by a variant, exit at target / stop / timeout (RULES.md 9).

A setup is known from `known_at` on (the bar its last swing point was confirmed), never earlier: no look-ahead.
Variants, so the report shows what each confirmation adds:
  touch          enter at the near edge of the zone when price first touches it
  close          ... wait (max `confirm_bars`) for a close of the setup's own timeframe on the reversal side of the
                 zone, enter at that close (RULES.md 7)
  close+ltf      ... and an LTF signal (1h SFP or regular RSI/CVD divergence in the trade's direction) confirmed
                 between the touch and that close
Exit: target first = win, stop (the invalidation level) first = loss, neither within `max_hold` bars = timeout at
the close. When one bar reaches both, the stop is assumed first (we cannot see inside the bar). Fees per side.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta

from signals.data.candles import Candle
from signals.patterns.fib import Zone

LONG, SHORT = "long", "short"
TOUCH, CLOSE, CLOSE_LTF = "touch", "close", "close+ltf"
VARIANTS = (TOUCH, CLOSE, CLOSE_LTF)
WIN, LOSS, TIMEOUT = "win", "loss", "timeout"


@dataclass(frozen=True)
class Params:
    max_wait: int = 60          # bars to wait for the zone after the setup is known
    confirm_bars: int = 5       # bars after the touch to get the reversal close (RULES.md 7)
    max_hold: int = 60          # bars to hold before a timeout exit
    fee: float = 0.001          # per side (0.1%: Binance spot taker)


@dataclass(frozen=True)
class Setup:
    rule: str                   # e.g. "Elliott wave-5 zone (impulse)", "Harmonic Bat PRZ"
    asset: str
    timeframe: str
    direction: str              # LONG or SHORT: the trade taken at the zone
    known_at: int               # bar index in the setup's candles
    zone: Zone
    invalidation: float         # stop: the plan is wrong beyond it
    target: float
    source: str = ""            # the swing points it came from, for the trade list


@dataclass(frozen=True)
class Trade:
    setup: Setup
    variant: str
    entry_index: int
    entry_price: float
    exit_index: int
    exit_price: float
    outcome: str
    r: float                    # result in multiples of the risk (entry to stop), after fees
    entry_time: datetime


# an LTF check: (start, end, direction) -> was there a confirming 1h signal in that window?
LtfCheck = Callable[[datetime, datetime, str], bool]


def _beyond_stop(bar: Candle, setup: Setup) -> bool:
    return bar.high >= setup.invalidation if setup.direction == SHORT else bar.low <= setup.invalidation


def _touches(bar: Candle, setup: Setup) -> bool:
    return bar.high >= setup.zone.low if setup.direction == SHORT else bar.low <= setup.zone.high


def _reversal_close(bar: Candle, setup: Setup) -> bool:
    return bar.close < setup.zone.low if setup.direction == SHORT else bar.close > setup.zone.high


def simulate(candles: Sequence[Candle], setup: Setup, variant: str, params: Params = Params(),
             ltf: LtfCheck | None = None, bar_span: timedelta = timedelta(days=1)) -> Trade | None:
    """One trade for the setup and variant, or None when no entry happened (zone never reached, plan invalidated
    first, no confirmation in time, or a target/stop on the wrong side of the entry)."""
    sign = 1 if setup.direction == LONG else -1
    end_wait = min(len(candles), setup.known_at + 1 + params.max_wait)

    touch = None
    for i in range(setup.known_at + 1, end_wait):
        if _touches(candles[i], setup):
            touch = i
            break
        if _beyond_stop(candles[i], setup):
            return None
    if touch is None:
        return None

    if variant == TOUCH:
        entry_index = touch
        entry_price = setup.zone.low if setup.direction == SHORT else setup.zone.high
        first_exit_bar = touch                       # the touch bar itself may already hit the stop
    else:
        entry_index = None
        for i in range(touch, min(len(candles), touch + params.confirm_bars)):
            if _beyond_stop(candles[i], setup):
                return None                          # the plan failed before it was confirmed
            if _reversal_close(candles[i], setup):
                entry_index = i
                break
        if entry_index is None:
            return None
        if variant == CLOSE_LTF:
            if ltf is None or not ltf(candles[touch].time, candles[entry_index].time + bar_span, setup.direction):
                return None
        entry_price = candles[entry_index].close
        first_exit_bar = entry_index + 1

    risk = (entry_price - setup.invalidation) * sign
    reward = (setup.target - entry_price) * sign
    if risk <= 0 or reward <= 0:
        return None

    outcome, exit_index, exit_price = TIMEOUT, None, None
    last = min(len(candles), first_exit_bar + params.max_hold)
    for i in range(first_exit_bar, last):
        bar = candles[i]
        if _beyond_stop(bar, setup):
            outcome, exit_index, exit_price = LOSS, i, setup.invalidation
            break
        hit_target = bar.low <= setup.target if setup.direction == SHORT else bar.high >= setup.target
        if hit_target:
            outcome, exit_index, exit_price = WIN, i, setup.target
            break
    if exit_index is None:
        if last <= first_exit_bar:
            return None                              # no bar left after the entry (end of the data)
        exit_index = last - 1
        exit_price = candles[exit_index].close

    fee_r = 2 * params.fee * entry_price / risk
    r = (exit_price - entry_price) * sign / risk - fee_r
    return Trade(setup, variant, entry_index, entry_price, exit_index, exit_price, outcome, r,
                 candles[entry_index].time)
