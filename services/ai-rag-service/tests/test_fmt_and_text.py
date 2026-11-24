from datetime import timezone

from core.fmt import date_tr, num, parse_time, pct, tl
from core.text import tr_lower


def test_turkish_number_formats():
    assert tl(12500.4) == "12.500 TL"
    assert tl(1_000_000) == "1.000.000 TL"
    assert num(1.39, 1) == "1,4"
    assert num(3.0, 1) == "3"
    assert num(-2000) == "-2.000"
    assert pct(0.1333) == "%13"
    assert pct(0.36) == "%36"


def test_dotnet_times_parse_and_print_in_words():
    t = parse_time("2026-11-10T10:00:00.1234567")   # 7 fraction digits, no zone
    assert t.tzinfo == timezone.utc and t.day == 10
    assert parse_time("2026-11-20T10:00:00Z").tzinfo is not None
    assert date_tr(t) == "10 Kasım 2026"


def test_turkish_lowercase():
    assert tr_lower("IŞIK İzmir") == "ışık izmir"
    assert tr_lower("Finansal IQ") == "finansal iq"
