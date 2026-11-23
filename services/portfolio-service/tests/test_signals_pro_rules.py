"""Professional-level rules (signals/rules/PROFESSIONAL.md) on small hand-made series."""

from datetime import datetime, timedelta, timezone

import pytest

from signals.data.candles import Candle
from signals.data.derivatives import hourly, parse_funding, parse_metrics
from signals.rules import pro_detect as pr
from signals.rules.pa_detect import DOWN, UP, Break
from signals.rules.smc_detect import Zone
from signals.structure.sfp import BEARISH, Sfp, find_open_sfps, find_sfps

T0 = datetime(2026, 1, 5, tzinfo=timezone.utc)


def bar(i, o, h, lo, c, v=1.0, taker=None, step=timedelta(hours=1), start=T0):
    return Candle(time=start + i * step, open=o, high=h, low=lo, close=c, volume=v, taker_buy_volume=taker)


def test_poc_is_where_the_volume_is_and_the_value_area_holds_70_percent():
    cs = [bar(0, 10, 20, 10, 20, 10)] + [bar(i, 14, 15, 14, 15, 100) for i in range(1, 6)]
    p = pr.volume_profile(cs, bins=10)
    assert 14 <= p.poc <= 15 and p.val <= p.poc <= p.vah
    inside = sum(v for k, v in enumerate(p.bins) if p.val <= 10 + k + 0.5 <= p.vah)
    assert inside >= 0.7 * p.volume
    assert sum(p.bins) == pytest.approx(510)


def test_naked_poc_until_price_comes_back():
    day1 = [bar(i, 100, 102, 99, 101, 10) for i in range(24)]
    day2 = [bar(24 + i, 120, 122, 118, 121, 10) for i in range(24)]
    cs = day1 + day2 + [bar(48, 118, 119, 95, 98, 10)]
    first, second, _ = pr.session_profiles(cs)
    assert pr.poc_touch(cs, first) == 48 and pr.poc_touch(cs[:48], first) is None
    assert second.start == T0 + timedelta(days=1)


def test_gap_fill_states():
    zone = Zone("FVG", UP, 0, 100, 110, 0)
    base = [bar(0, 115, 116, 112, 115)]
    for low, state in ((111, pr.UNTOUCHED), (108, pr.PARTIAL), (105, pr.HALF), (99, pr.FULL)):
        assert pr.fill_state(base + [bar(1, 115, 116, low, 114)], zone) == state
    mirror = Zone("FVG", DOWN, 0, 100, 110, 0)
    assert pr.fill_state(base + [bar(1, 90, 106, 89, 95)], mirror) == pr.HALF


def test_sfp_plan_follows_the_lesson():
    """The lesson's short (BTC, January 2026): 1 = 94,789.08, 0 = 91,264.6, entry 93,505.54, stop 94,930.83, target 91,305.5."""
    one, zero = 94789.08, 91264.6
    h4 = timedelta(hours=4)
    htf = [bar(0, 94000, one, 93800, 94100, step=h4)]
    path = [94700, 94300, 93900, 93100, 92000, zero, 92500, 93000, 93600, 93200, 92000]
    ltf = [bar(0, 94000, one, 93900, 94100, step=timedelta(minutes=15))] + [
        Candle(time=T0 + h4 + i * timedelta(minutes=15), open=v, high=v, low=v, close=v, volume=1) for i, v in enumerate(path)]
    s = Sfp(BEARISH, 94588.99, 0, 0, 0, 1, one)
    plan, = pr.sfp_msb_plans(htf, h4, [s], ltf, [Break("MSB", DOWN, 4, 93250, 1)])
    assert plan.entry == pytest.approx(93516.7, abs=1) and plan.end == zero and plan.touch == 9
    assert plan.stop == pytest.approx(94930.1, abs=1) and plan.risk_reward == pytest.approx(1.59, abs=0.02)
    assert pr.sfp_msb_plans(htf, h4, [s], ltf, [Break("MSB", UP, 4, 93250, 1)]) == []
    higher = list(ltf)
    higher[2] = Candle(time=ltf[2].time, open=94300, high=95000, low=94300, close=94300, volume=1)          # the extreme did not hold
    assert pr.sfp_msb_plans(htf, h4, [s], higher, [Break("MSB", DOWN, 4, 93250, 1)]) == []


def tops(*extra):
    """A high at 120 (bar 6), a newer lower high at 110 (bar 18), then `extra` (high, close) bars."""
    rows = [(100, 100)] * 6 + [(120, 100)] + [(100, 100)] * 11 + [(110, 100)] + [(100, 100)] * 8 + list(extra)
    return [Candle(time=T0 + i * timedelta(hours=1), open=100, high=h, low=90 - i * 0.01, close=c, volume=1) for i, (h, c) in enumerate(rows)]


def test_open_sfp_sees_the_older_higher_high():
    cs = tops((125, 115))                                    # sweeps 110 and 120, closes above 110 but below 120
    got = [x for x in find_open_sfps(cs) if x.direction == BEARISH]
    assert [(x.level, x.extreme, x.candles) for x in got] == [(120, 125, 1)]
    assert [x for x in find_sfps(cs) if x.direction == BEARISH] == []          # the newest pivot (110) was closed beyond


def test_open_sfp_two_candles_real_break_and_one_use_per_level():
    two = [x for x in find_open_sfps(tops((125, 122), (123, 118))) if x.direction == BEARISH]
    assert [(x.level, x.sweep_index, x.confirmed_at, x.extreme) for x in two] == [(120, 27, 28, 125)]
    assert [x for x in find_open_sfps(tops((125, 122), (126, 124), (126, 118))) if x.direction == BEARISH] == []
    assert len([x for x in find_open_sfps(tops((125, 105), (126, 105))) if x.direction == BEARISH]) == 1


def weekend(start, friday, sunday):
    out, t = [], start
    while t < start + timedelta(days=4):
        price = friday if t < start + timedelta(days=1, hours=12) else sunday
        out.append(Candle(time=t, open=price, high=price + 1, low=price - 1, close=price, volume=1))
        t += timedelta(hours=1)
    return out


def test_weekend_gap_uses_chicago_hours_and_ends_with_24_7_trading():
    cs = weekend(datetime(2025, 1, 10, tzinfo=timezone.utc), 1000, 1050)          # Friday; winter time
    gap, = pr.weekend_gaps(cs)
    assert gap.close_time.hour == 22 and gap.open_time.hour == 23 and gap.up and (gap.close, gap.open) == (1000, 1050)
    assert pr.gap_filled_at(cs, gap) is None and pr.gap_filled_at(cs, gap, 1050) == gap.open_index
    summer, = pr.weekend_gaps(weekend(datetime(2025, 7, 11, tzinfo=timezone.utc), 1000, 1050))
    assert summer.close_time.hour == 21
    assert pr.weekend_gaps(weekend(datetime(2026, 7, 10, tzinfo=timezone.utc), 1000, 1050)) == []


def test_absorption_needs_flat_price_and_a_strong_delta():
    quiet = [bar(i, 100, 101, 99, 100, 10, 5.5 if i % 2 else 4.5) for i in range(150)]
    sold = [bar(150 + i, 100, 101, 99, 100, 10, 1) for i in range(12)]
    found = pr.absorption(quiet + sold)
    assert found and all(d == UP for _, d in found) and pr.absorption(quiet) == []
    assert pr.absorption([bar(i, 100, 101, 99, 100) for i in range(200)]) == []           # no taker data (futures)


def test_oi_quadrants():
    assert pr.oi_quadrant(1, 1) == "OI↑ fiyat↑" and pr.oi_quadrant(-1, 1) == "OI↑ fiyat↓"
    assert pr.oi_quadrant(1, -1) == "OI↓ fiyat↑" and pr.oi_quadrant(-1, -1) == "OI↓ fiyat↓"


def test_open_interest_is_the_last_value_known_at_the_full_hour():
    text = ("create_time,symbol,sum_open_interest\n2026-01-05 01:05:00,BTCUSDT,30\n2026-01-05 00:55:00,BTCUSDT,20\n"
            "2026-01-05 00:00:00,BTCUSDT,10\n2026-01-05 05:00:00,BTCUSDT,\n2026-01-05 04:30:00,BTCUSDT,50\n")
    got = hourly(parse_metrics(text))
    assert [(t.hour, v) for t, v in got] == [(0, 10), (1, 20), (2, 30)]                   # 03:00 and 04:00: older than an hour


def test_funding_rows():
    got = parse_funding("calc_time,funding_interval_hours,last_funding_rate\n1767571200001,8,0.0001\n")
    assert got[0][0].date().isoformat() == "2026-01-05" and got[0][1] == 0.0001
