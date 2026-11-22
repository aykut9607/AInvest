from datetime import date, datetime, timezone

from signals.data.download import (
    binance_days_of_current_month,
    binance_months,
    dedupe_sorted,
    kline_time_to_utc,
    parse_binance_kline_csv,
    parse_checksum,
)

# a real-looking Binance kline row: open_time, open, high, low, close, volume, close_time, quote_volume, trades,
# taker_buy_volume, taker_buy_quote_volume, ignore
ROW_MS = "1704067200000,42283.58,42554.57,42261.02,42475.23,1271.68,1704070799999,53957000.1,47134,682.36,28950000.5,0"
ROW_US = "1735689600000000,93576.00,94509.42,93489.03,94401.14,673.04,1735693199999999,63388000.2,98234,341.2,32140000.7,0"


def test_millisecond_and_microsecond_timestamps_give_the_same_kind_of_utc_time():
    assert kline_time_to_utc("1704067200000") == datetime(2024, 1, 1, tzinfo=timezone.utc)
    # spot files from 2025 on use microseconds
    assert kline_time_to_utc("1735689600000000") == datetime(2025, 1, 1, tzinfo=timezone.utc)


def test_kline_rows_are_parsed_and_a_header_line_is_skipped():
    text = "open_time,open,high,low,close,volume,close_time,quote_volume,count,taker_buy_volume,taker_buy_quote_volume,ignore\n" \
           + ROW_MS + "\n" + ROW_US + "\n"

    rows = parse_binance_kline_csv(text)

    assert [r["open_time"] for r in rows] == ["2024-01-01T00:00:00+00:00", "2025-01-01T00:00:00+00:00"]
    assert rows[0]["close"] == "42475.23"
    # taker-buy volume is kept: CVD is built from it
    assert rows[0]["taker_buy_volume"] == "682.36"


def test_checksum_file_gives_the_hash():
    assert parse_checksum("ABCDEF0123  BTCUSDT-1h-2024-01.zip\n") == "abcdef0123"


def test_monthly_archives_run_up_to_the_month_before_today():
    months = binance_months(date(2017, 8, 1), date(2026, 11, 23))

    assert months[0] == date(2017, 8, 1)
    assert months[-1] == date(2026, 10, 1)
    assert len(months) == 111


def test_daily_archives_cover_the_running_month_before_today():
    days = binance_days_of_current_month(date(2026, 11, 23))

    assert days[0] == date(2026, 11, 1)
    assert days[-1] == date(2026, 11, 22)


def test_overlapping_rows_are_kept_once_and_sorted():
    rows = [{"open_time": "b", "close": "2"}, {"open_time": "a", "close": "1"}, {"open_time": "b", "close": "2"}]

    assert [r["open_time"] for r in dedupe_sorted(rows)] == ["a", "b"]
