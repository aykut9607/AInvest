from datetime import datetime, timedelta, timezone

from signals.data.candles import Candle
from signals.indicators.cvd import cvd, cvd_divergences
from signals.indicators.rsi_divergence import (
    HIDDEN_BULLISH,
    REGULAR_BEARISH,
    REGULAR_BULLISH,
    DivergenceSettings,
    divergences,
    rma,
    rsi,
)
from signals.structure.pivots import HIGH, LOW, pivot_highs, pivot_lows
from signals.structure.sfp import BEARISH, BULLISH, find_sfps
from signals.structure.zigzag import wilder_atr, zigzag

T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def bar(i, o, h, l, c, v=1.0, buy=None):
    return Candle(time=T0 + timedelta(hours=i), open=o, high=h, low=l, close=c, volume=v, taker_buy_volume=buy)


def bars_from_closes(closes, spread=0.5):
    return [bar(i, c, c + spread, c - spread, c) for i, c in enumerate(closes)]


# ---------- pivots ----------

def test_pivot_high_needs_left_strictly_lower_and_right_not_higher():
    values = [1, 2, 3, 9, 3, 2, 1]
    [p] = pivot_highs(values, left=3, right=3)
    assert (p.kind, p.index, p.value, p.confirmed_at) == (HIGH, 3, 9, 6)


def test_pivot_is_only_known_after_the_right_bars():
    values = [5, 4, 3, 1, 3, 4]          # the low at index 3 needs 3 bars on the right: only 2 exist
    assert pivot_lows(values, left=3, right=3) == []
    assert pivot_lows(values + [5], left=3, right=3)[0].confirmed_at == 6


def test_of_two_equal_highs_the_first_is_the_pivot():
    values = [1, 2, 9, 9, 2, 1, 0]
    assert [p.index for p in pivot_highs(values, left=2, right=2)] == [2]


def test_missing_values_never_form_a_pivot():
    # an indicator's warm-up (None) inside the window: no pivot; once the window is complete: pivot
    assert pivot_lows([None, 5, 0, 5, 6], left=2, right=2) == []
    assert pivot_lows([None, 3, 2, 0, 1, 2], left=2, right=2)[0].index == 3


# ---------- RSI (TradingView ta.rsi) ----------

def test_rma_is_seeded_with_the_simple_average():
    assert rma([2, 4, 6, 8], 3) == [None, None, 4.0, (4.0 * 2 + 8) / 3]


def test_rsi_extremes_and_warm_up():
    rising = rsi([float(i) for i in range(20)], 14)
    assert rising[:14] == [None] * 14 and rising[14] == 100.0
    falling = rsi([float(20 - i) for i in range(20)], 14)
    assert falling[14] == 0.0


def test_rsi_matches_the_textbook_wilder_example():
    # the classic 14-period example (StockCharts): gains 3.34 / 14, losses 1.40 / 14 -> RS 2.386 -> RSI 70.46
    # (the textbook prints 70.53 because its table rounds the averages to 0.24 and 0.10 first)
    closes = [44.34, 44.09, 44.15, 43.61, 44.33, 44.83, 45.10, 45.42, 45.84, 46.08, 45.89, 46.03, 45.61, 46.28, 46.28]
    assert round(rsi(closes, 14)[14], 2) == 70.46


# ---------- divergences (SERS41 RSI logic) ----------

def _osc_and_candles(lows_at_pivots):
    """Two oscillator lows 10 bars apart; price lows at those bars given by the test."""
    osc = [50.0] * 30
    osc[5], osc[15] = lows_at_pivots[0][1], lows_at_pivots[1][1]
    candles = [bar(i, 100, 101, 99, 100) for i in range(30)]
    candles[5] = bar(5, 100, 101, lows_at_pivots[0][0], 100)
    candles[15] = bar(15, 100, 101, lows_at_pivots[1][0], 100)
    return osc, candles


def test_price_lower_low_with_oscillator_higher_low_is_pu():
    osc, candles = _osc_and_candles([(95.0, 30.0), (93.0, 35.0)])   # price LL, osc HL

    [d] = divergences(candles, osc, "RSI")

    assert (d.kind, d.pivot_index, d.previous_index, d.confirmed_at) == (REGULAR_BULLISH, 15, 5, 20)


def test_price_higher_low_with_oscillator_lower_low_is_hidden_bullish():
    osc, candles = _osc_and_candles([(95.0, 35.0), (97.0, 30.0)])
    assert divergences(candles, osc, "RSI")[0].kind == HIDDEN_BULLISH


def test_pivots_too_close_together_are_not_compared():
    osc = [50.0] * 30
    osc[5], osc[9] = 30.0, 35.0       # 4 bars apart: below the 5-bar minimum of the indicator
    candles = [bar(i, 100, 101, 99, 100) for i in range(30)]
    candles[9] = bar(9, 100, 101, 90, 100)
    assert divergences(candles, osc, "RSI", DivergenceSettings(lookback_left=3, lookback_right=3)) == []


def test_price_higher_high_with_oscillator_lower_high_is_nu():
    osc = [50.0] * 30
    osc[5], osc[15] = 75.0, 70.0
    candles = [bar(i, 100, 101, 99, 100) for i in range(30)]
    candles[5] = bar(5, 100, 105, 99, 100)
    candles[15] = bar(15, 100, 108, 99, 100)
    assert [d.kind for d in divergences(candles, osc, "RSI")] == [REGULAR_BEARISH]


# ---------- CVD ----------

def test_cvd_is_the_running_sum_of_buy_minus_sell():
    candles = [bar(0, 1, 1, 1, 1, v=10, buy=7), bar(1, 1, 1, 1, 1, v=10, buy=2)]
    assert cvd(candles) == [4.0, -2.0]


def test_futures_without_buy_volume_have_no_cvd_divergence():
    candles = [bar(i, 1, 1, 1, 1) for i in range(40)]
    assert cvd_divergences(candles) == []


# ---------- SFP ----------

def _with_low_pivot_at_100():
    """A clear pivot low of 100 at bar 5, confirmed at bar 10 (5/5), price around 105 after it."""
    candles = [bar(i, 106, 107, 104, 105) for i in range(16)]
    candles[5] = bar(5, 104, 105, 100, 103)
    return candles


def test_one_candle_sfp_wick_below_close_above():
    candles = _with_low_pivot_at_100()
    candles[12] = bar(12, 104, 105, 98, 101)       # sweeps 100, closes 101

    [s] = [s for s in find_sfps(candles) if s.direction == BULLISH]

    assert (s.level, s.sweep_index, s.confirmed_at, s.candles, s.extreme) == (100, 12, 12, 1, 98)


def test_two_candle_sfp_close_below_then_next_close_above():
    candles = _with_low_pivot_at_100()
    candles[12] = bar(12, 104, 104, 97, 99)        # closes below 100
    candles[13] = bar(13, 99, 103, 98, 102)        # next candle closes back above

    [s] = [s for s in find_sfps(candles) if s.direction == BULLISH]

    assert (s.confirmed_at, s.candles, s.extreme) == (13, 2, 97)


def test_a_real_break_is_not_an_sfp_and_the_level_is_dropped():
    candles = _with_low_pivot_at_100()
    candles[12] = bar(12, 104, 104, 97, 99)        # closes below
    candles[13] = bar(13, 99, 99.5, 96, 98)        # stays below: real breakdown
    candles[14] = bar(14, 98, 103, 97, 102)        # later recovery does not make it an SFP

    assert [s for s in find_sfps(candles) if s.direction == BULLISH] == []


def test_a_pivot_not_yet_confirmed_cannot_be_swept():
    candles = _with_low_pivot_at_100()
    candles[8] = bar(8, 104, 105, 99, 101)         # sweeps 100 at bar 8, but the pivot is only known at bar 10
    assert [s for s in find_sfps(candles) if s.direction == BULLISH and s.sweep_index == 8] == []


def test_bearish_sfp_above_a_pivot_high():
    candles = [bar(i, 104, 105, 103, 104) for i in range(16)]
    candles[5] = bar(5, 105, 110, 104, 106)
    candles[12] = bar(12, 106, 112, 105, 108)      # above 110, closes below

    assert [(s.direction, s.level) for s in find_sfps(candles)] == [(BEARISH, 110)]


# ---------- ZigZag ----------

def test_atr_uses_wilder_smoothing():
    candles = [bar(i, 10, 12, 10, 11) for i in range(3)]   # true range 2 every bar
    assert wilder_atr(candles, 2) == [None, 2.0, 2.0]


def test_zigzag_alternates_and_ignores_small_wiggles():
    # up to 120, small dip, down to 90, up to 115: with a big threshold only the main turns count
    path = [100 + i for i in range(21)] + [119, 120, 118] + [118 - 2 * i for i in range(15)] + [90 + 2 * i for i in range(13)]
    candles = bars_from_closes(path)

    points = zigzag(candles, multiple=6.0, atr_length=3)

    # the start of the rise is a bottom too: bottom -> top 120 -> bottom 90, the 119/120/118 wiggle is not a turn
    assert [p.kind for p in points] == [LOW, HIGH, LOW]
    assert points[1].price == max(c.high for c in candles)
    assert points[2].price == min(c.low for c in candles[20:])
    assert all(p.confirmed_at > p.index for p in points)
