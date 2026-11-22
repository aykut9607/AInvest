from datetime import date, datetime, timedelta, timezone

from signals.data.candles import (
    Candle,
    bucket_start_minutes,
    bucket_start_week,
    es_roll_days,
    gold_roll_days,
    is_consistent,
    load_series,
    resample,
    third_friday,
    without_days,
)

UTC = timezone.utc


def candle(t: datetime, o=10.0, h=12.0, l=9.0, c=11.0, v=1.0, buy=None) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v, taker_buy_volume=buy)


def test_45_minute_blocks_start_at_utc_midnight():
    assert bucket_start_minutes(datetime(2026, 1, 5, 0, 44, tzinfo=UTC), 45) == datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    assert bucket_start_minutes(datetime(2026, 1, 5, 0, 45, tzinfo=UTC), 45) == datetime(2026, 1, 5, 0, 45, tzinfo=UTC)
    # 32 x 45 minutes = one day: the last block of the day starts at 23:15
    assert bucket_start_minutes(datetime(2026, 1, 5, 23, 59, tzinfo=UTC), 45) == datetime(2026, 1, 5, 23, 15, tzinfo=UTC)


def test_weeks_start_on_monday():
    sunday = datetime(2026, 11, 22, 18, 0, tzinfo=UTC)
    assert bucket_start_week(sunday) == datetime(2026, 11, 16, tzinfo=UTC)


def test_three_15m_candles_make_one_45m_candle():
    t0 = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    parts = [candle(t0, o=10, h=12, l=9, c=11, v=1, buy=0.6),
             candle(t0 + timedelta(minutes=15), o=11, h=15, l=10, c=14, v=2, buy=1.5),
             candle(t0 + timedelta(minutes=30), o=14, h=14, l=8, c=9, v=3, buy=0.5)]

    merged, incomplete = resample(parts, lambda t: bucket_start_minutes(t, 45), expected_parts=3)

    assert incomplete == 0
    assert merged == [Candle(time=t0, open=10, high=15, low=8, close=9, volume=6, taker_buy_volume=2.6)]


def test_a_bucket_with_a_missing_part_is_dropped_when_parts_are_expected():
    t0 = datetime(2026, 1, 5, 0, 0, tzinfo=UTC)
    parts = [candle(t0), candle(t0 + timedelta(minutes=15))]  # the exchange was down for the third one

    merged, incomplete = resample(parts, lambda t: bucket_start_minutes(t, 45), expected_parts=3)

    assert merged == [] and incomplete == 1


def test_open_or_close_outside_the_range_is_inconsistent():
    t = datetime(2004, 3, 19, tzinfo=UTC)
    assert is_consistent(candle(t, o=10, h=12, l=9, c=11))
    # ES 2004-03-19: close 1120.18 below the low 1122 (expiry settlement)
    assert not is_consistent(candle(t, o=1124.75, h=1128, l=1122, c=1120.18))


def test_es_rolls_on_the_third_friday_of_each_quarter():
    assert third_friday(2024, 12) == date(2024, 12, 20)
    assert third_friday(2025, 3) == date(2025, 3, 21)
    assert {date(2025, 3, 21), date(2025, 6, 20), date(2025, 9, 19), date(2025, 12, 19)} <= es_roll_days(2025, 2025)


def test_gold_roll_day_is_the_low_volume_day_before_the_jump():
    days = [datetime(2025, 7, 28, tzinfo=UTC), datetime(2025, 7, 29, tzinfo=UTC),
            datetime(2025, 7, 30, tzinfo=UTC), datetime(2025, 7, 31, tzinfo=UTC)]
    volumes = [180_215, 113_144, 19_252, 158_029]   # the real GC=F numbers around the July 2025 roll
    daily = [candle(t, v=v) for t, v in zip(days, volumes)]

    assert gold_roll_days(daily) == {date(2025, 7, 30)}


def test_a_volume_jump_outside_the_roll_window_is_not_a_roll():
    # mid-June, and June is not a month whose last week holds a roll
    daily = [candle(datetime(2025, 6, 10, tzinfo=UTC), v=1000), candle(datetime(2025, 6, 11, tzinfo=UTC), v=9000),
             candle(datetime(2025, 6, 27, tzinfo=UTC), v=1000), candle(datetime(2025, 6, 30, tzinfo=UTC), v=9000)]

    assert gold_roll_days(daily) == set()


def test_candles_of_roll_days_are_removed():
    hours = [candle(datetime(2025, 7, 29, 23, tzinfo=UTC)), candle(datetime(2025, 7, 30, 7, tzinfo=UTC)),
             candle(datetime(2025, 7, 31, 1, tzinfo=UTC))]

    kept, removed = without_days(hours, {date(2025, 7, 30)})

    assert removed == 1
    assert [c.time.day for c in kept] == [29, 31]


def _write(path, rows, header="open_time,open,high,low,close,volume,quote_volume,trades,taker_buy_volume,taker_buy_quote_volume"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(header + "\n" + "\n".join(rows) + "\n", encoding="utf-8")


def test_btc_weekly_is_built_from_seven_daily_candles_and_the_running_week_is_left_out(tmp_path):
    monday = datetime(2026, 11, 9, tzinfo=UTC)
    rows = [f"{(monday + timedelta(days=i)).isoformat()},{100 + i},{110 + i},{90 + i},{105 + i},1,0,0,0.5,0" for i in range(13)]
    _write(tmp_path / "binance" / "BTCUSDT" / "1d.csv", rows)   # one full week + 6 days of the next

    series = load_series("BTCUSDT", "1w", raw_dir=tmp_path)

    assert [c.time for c in series.candles] == [monday]
    assert series.candles[0].open == 100 and series.candles[0].close == 111 and series.candles[0].volume == 7
    assert series.dropped["incomplete_buckets"] == 1


def test_gold_daily_starts_in_2012(tmp_path):
    rows = ["2011-12-30T05:00:00+00:00,1,2,0.5,1.5,10", "2012-01-03T05:00:00+00:00,1,2,0.5,1.5,10"]
    _write(tmp_path / "yahoo" / "GC_F" / "1d.csv", rows, header="open_time,open,high,low,close,volume")

    series = load_series("GC", "1d", raw_dir=tmp_path)

    assert [c.time.year for c in series.candles] == [2012]
    assert series.dropped["gold_before_2012"] == 1
