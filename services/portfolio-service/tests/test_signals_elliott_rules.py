"""Each numbered rule of signals/rules/ELLIOTT.md that prices can break, one example per rule (own numbers)."""

import pytest

from signals.rules.elliott_check import (
    GUIDE, UNKNOWN, check_diagonal, check_flat, check_impulse, check_triangle, check_zigzag, judge)
from signals.rules.elliott_draw import handbook

VALID = [50, 70, 60, 98, 82, 104]


def broken(verdict):
    return [f.rule for f in verdict.violations]


def test_valid_impulse_and_its_mirror_are_only_possible():
    for prices in (VALID, [-p for p in VALID], [104, 84, 94, 56, 72, 50]):
        verdict = check_impulse(prices)
        assert verdict.possible
        assert "E-05" in [f.rule for f in verdict.findings if f.level == UNKNOWN]    # never "certain" from prices alone


@pytest.mark.parametrize("prices, rule", [
    ([50, 70, 47, 98, 82, 104], "E-01"),
    ([50, 70, 50, 98, 82, 104], "E-01"),       # exactly 100% is also invalid
    ([50, 70, 58, 68], "E-02"),
    ([50, 74, 64, 84, 76, 102], "E-03"),
    ([50, 70, 60, 98, 66, 104], "E-04"),
    ([50, 70, 60, 98, 70, 104], "E-04"),       # touching wave 1's end is overlap
])
def test_impulse_hard_rules(prices, rule):
    assert broken(check_impulse(prices)) == [rule]
    assert broken(check_impulse([200 - p for p in prices])) == [rule]


def test_wave_3_need_not_be_the_longest():
    assert check_impulse([50, 70, 60, 78, 72, 85]).possible          # 20 / 18 / 13: the shortest is wave 5


def test_a_wick_inside_wave_4_counts():
    assert check_impulse([50, 70, 60, 98, 78, 104], wave4_path_extreme=72).possible
    assert broken(check_impulse([50, 70, 60, 98, 78, 104], wave4_path_extreme=67)) == ["E-04"]


def test_truncated_fifth_is_a_warning_not_a_violation():
    verdict = check_impulse([50, 70, 60, 104, 84, 100])
    assert verdict.possible and "E-17" in [f.rule for f in verdict.findings if f.level == GUIDE]


@pytest.mark.parametrize("prices, rule", [
    ([60, 100, 58, 94, 80, 90], "E-21"),
    ([60, 100, 76, 98, 80, 90], "E-22"),
    ([60, 100, 76, 110, 72, 116], "E-23"),
    ([60, 100, 76, 110, 94, 132], "E-24"),
    ([60, 100, 90, 125, 97, 120], "E-26"),     # 1-3 rises faster than 2-4: the lines diverge
])
def test_diagonal_rules(prices, rule):
    assert rule in broken(check_diagonal(prices))


def test_contracting_diagonal_is_possible():
    assert check_diagonal([60, 100, 76, 110, 94, 116]).possible
    assert check_diagonal([116, 76, 100, 66, 82, 60]).possible


def test_zigzag_b_beyond_the_start_is_not_a_zigzag_and_deep_b_is_only_suspect():
    assert broken(check_zigzag([100, 76, 103, 62])) == ["E-31"]
    deep = check_zigzag([100, 76, 96, 70])
    assert deep.possible and "E-33" in [f.rule for f in deep.findings if f.level == GUIDE]


@pytest.mark.parametrize("prices, kind", [([100, 80, 98, 78], "normal"), ([100, 80, 105, 72], "genişleyen"),
                                          ([100, 80, 106, 84], "kaçan")])
def test_flat_kinds(prices, kind):
    assert any(f.rule == "E-41" and kind in f.text for f in check_flat(prices).findings)


def test_triangle_must_contract():
    assert check_triangle([100, 70, 94, 76, 89, 80]).possible
    assert broken(check_triangle([100, 70, 94, 76, 97, 80])) == ["E-52"]


def test_judge_puts_possible_models_first_and_rejects_bad_input():
    assert judge(VALID)[0].model == "impulse"
    assert judge([60, 100, 76, 110, 94, 116])[0].model == "diagonal"
    with pytest.raises(ValueError):
        judge([1, 2, 3, 4])                    # does not alternate
    with pytest.raises(ValueError):
        judge([1, 2])


def test_handbook_draws_without_external_resources():
    page = handbook()
    assert page.count("<svg") > 20 and "http" not in page
