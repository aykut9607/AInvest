from datetime import datetime, timedelta, timezone

from signals.backtest.engine import CLOSE, CLOSE_LTF, LONG, LOSS, SHORT, TIMEOUT, TOUCH, WIN, Params, Setup, simulate
from signals.backtest.report import wilson, worst_streak
from signals.data.candles import Candle
from signals.patterns.fib import Zone

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
NO_FEE = Params(max_wait=10, confirm_bars=3, max_hold=10, fee=0.0)


def bar(i, o, h, l, c):
    return Candle(time=T0 + timedelta(days=i), open=o, high=h, low=l, close=c, volume=1.0)


def short_setup(known_at=0):
    # sell the 110-112 zone, stop 115, target 100
    return Setup("test", "X", "1d", SHORT, known_at, Zone(110, 112), 115.0, 100.0)


def test_touch_entry_at_the_zone_edge_then_target():
    candles = [bar(0, 100, 101, 99, 100), bar(1, 105, 111, 104, 109), bar(2, 109, 109, 99, 100)]

    trade = simulate(candles, short_setup(), TOUCH, NO_FEE)

    assert (trade.entry_price, trade.outcome, trade.exit_index) == (110, WIN, 2)
    assert trade.r == (110 - 100) / (115 - 110)          # +2R


def test_stop_and_target_in_the_same_bar_counts_as_stop():
    candles = [bar(0, 100, 101, 99, 100), bar(1, 105, 111, 104, 109), bar(2, 109, 116, 99, 100)]
    assert simulate(candles, short_setup(), TOUCH, NO_FEE).outcome == LOSS


def test_close_variant_waits_for_a_close_below_the_zone():
    candles = [bar(0, 100, 101, 99, 100), bar(1, 105, 111, 104, 110.5),   # touch, closes inside the zone
               bar(2, 110, 111, 107, 108),                                # closes below 110: confirmation
               bar(3, 108, 108, 99, 100)]

    trade = simulate(candles, short_setup(), CLOSE, NO_FEE)

    assert (trade.entry_index, trade.entry_price, trade.outcome) == (2, 108, WIN)


def test_no_confirmation_in_time_means_no_trade():
    candles = [bar(0, 100, 101, 99, 100)] + [bar(i, 110, 111.5, 110, 111) for i in range(1, 8)]
    assert simulate(candles, short_setup(), CLOSE, NO_FEE) is None


def test_a_bar_through_the_zone_and_the_stop_is_a_loss():
    candles = [bar(0, 100, 101, 99, 100), bar(1, 100, 101, 99, 100)]
    long = Setup("test", "X", "1d", LONG, 0, Zone(90, 92), 85.0, 100.0)
    candles.append(bar(2, 100, 100, 84, 86))      # one bar falls through the zone and the stop: entry, then stop
    trade = simulate(candles, long, TOUCH, NO_FEE)
    assert trade.outcome == LOSS


def test_ltf_variant_needs_a_signal_in_the_window():
    candles = [bar(0, 100, 101, 99, 100), bar(1, 105, 111, 104, 109), bar(2, 109, 109, 99, 100)]
    assert simulate(candles, short_setup(), CLOSE_LTF, NO_FEE, ltf=lambda s, e, d: False) is None
    assert simulate(candles, short_setup(), CLOSE_LTF, NO_FEE, ltf=lambda s, e, d: d == SHORT).outcome == WIN


def test_timeout_exits_at_the_close():
    candles = [bar(0, 100, 101, 99, 100), bar(1, 105, 111, 104, 109)] + [bar(i, 108, 109, 107, 108) for i in range(2, 14)]
    trade = simulate(candles, short_setup(), TOUCH, NO_FEE)
    assert trade.outcome == TIMEOUT and trade.exit_price == 108


def test_fees_are_paid_in_r():
    candles = [bar(0, 100, 101, 99, 100), bar(1, 105, 111, 104, 109), bar(2, 109, 109, 99, 100)]
    trade = simulate(candles, short_setup(), TOUCH, Params(max_wait=10, confirm_bars=3, max_hold=10, fee=0.001))
    assert round(trade.r, 4) == round(2 - 2 * 0.001 * 110 / 5, 4)


def test_wilson_interval_is_wide_for_few_trades():
    low3, high3 = wilson(2, 3)
    low300, high300 = wilson(200, 300)
    assert high3 - low3 > 0.5 and high300 - low300 < 0.12
    assert wilson(0, 0) == (0.0, 0.0)


def test_worst_losing_streak():
    class T:  # minimal stand-in
        def __init__(self, i, outcome): self.entry_time, self.outcome = T0 + timedelta(days=i), outcome
    assert worst_streak([T(0, WIN), T(1, LOSS), T(2, TIMEOUT), T(3, LOSS), T(4, WIN)]) == 3
