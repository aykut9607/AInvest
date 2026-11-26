"""The rule tree at tops and bottoms: the parts that need no data files."""

from signals.scoring.confirm import elliott, harmonics
from signals.structure.zigzag import SwingPoint


def points(*prices):
    up = prices[1] > prices[0]
    return [SwingPoint("low" if (i % 2 == 0) == up else "high", i * 10, p, i * 10) for i, p in enumerate(prices)]


IMPULSE = (100, 110, 105, 130, 120, 138)


def test_a_finished_12345_is_found_with_its_kind():
    assert "12345 sonu|3. dalga uzayan" in elliott(points(*IMPULSE))
    assert not any(k.startswith("12345") for k in elliott(points(100, 110, 99, 130, 120, 138)))        # 2 below the start


def test_abc_needs_a_12345_before_it():
    assert any(k.startswith("ABC sonu|zigzag") for k in elliott(points(*IMPULSE, 122, 130, 112)))
    assert not any(k.startswith("ABC sonu") for k in elliott(points(138, 122, 130, 112)))
    assert any(k.startswith("ABC sonu") for k in elliott(points(138, 122, 130, 112), ended={0: 0}, known=99))   # the 12345 of a larger degree


def test_complex_corrections_follow_the_legs():
    assert "WXY sonu|tek bacak X" in elliott(points(*IMPULSE, 125, 131, 118, 128, 115, 121, 108))
    assert "X sonu|tek bacak X" in elliott(points(*IMPULSE, 125, 131, 118, 128))


def test_harmonics_follow_the_table():
    assert "Bat" in harmonics(points(100, 200, 152, 184, 111.4))
    assert "Cypher" in harmonics(points(100, 200, 150, 225, 126.75))
    assert "Gartley" not in harmonics(points(100, 200, 152, 184, 111.4))
