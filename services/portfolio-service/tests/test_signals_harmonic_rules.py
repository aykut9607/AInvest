"""Each numbered rule of signals/rules/HARMONIC.md that ratios can break."""

import pytest

from signals.rules.elliott_check import GUIDE
from signals.rules.harmonic_check import SPECS, check, judge, ratios
from signals.rules.harmonic_draw import VALID, build, handbook


def broken(verdict):
    return [f.rule for f in verdict.violations]


@pytest.mark.parametrize("name", list(SPECS))
def test_each_pattern_has_a_valid_example_and_its_mirror(name):
    prices = build(name, *VALID[name])
    assert broken(check(name, prices)) == []
    assert broken(check(name, [300 - p for p in prices])) == []
    assert broken(check(name, prices[:4])) == []                  # still developing
    assert judge(prices)[0].model == name


def test_ratios_use_absolute_legs():
    r = ratios([100, 200, 150, 180.9, 111.4])
    assert (round(r["B"], 3), round(r["C"], 3), round(r["D"], 3)) == (0.5, 0.618, 0.886)
    assert round(r["BC"], 2) == 2.25 and round(r["ABCD"], 2) == 1.39


@pytest.mark.parametrize("name, prices, rule", [
    ("Gartley", [100, 200, 145, 186, 121.4], "H-03"),
    ("Butterfly", build("Butterfly", 0.70, 0.618), "H-03"),
    ("Bat", build("Bat", 0.55, 0.618), "H-03"),
    ("Bat", build("Bat", 0.5, 0.30), "H-01"),                     # C too shallow
    ("Bat", build("Bat", 0.5, 0.95), "H-01"),                     # C too deep
    ("Bat", build("Bat", 0.5, 0.618, d=0.94), "H-04"),
    ("Gartley", [100, 200, 138.2, 184, 97], "H-06"),
    ("Bat", [100, 200, 150, 195, 136], "H-05"),
    ("Deep Crab", [100, 200, 98.5, 145, 38.2], "H-02"),           # no tolerance: B may never pass X
])
def test_rules(name, prices, rule):
    assert rule in broken(check(name, prices))


def test_a_crab_with_b_0382_can_never_satisfy_its_own_bc_range():
    for c in range(382, 887):
        assert "H-05" in broken(check("Crab", build("Crab", 0.382, c / 1000)))


def test_alternate_bat_has_no_stated_bc_maximum():
    assert broken(check("Alternate Bat", build("Alternate Bat", 0.30, 0.6))) == []


def test_gartley_abcd_is_a_guide():
    verdict = check("Gartley", build("Gartley", 0.618, 0.618))    # CD = 0.89 AB
    assert verdict.possible and "H-08" in [f.rule for f in verdict.findings if f.level == GUIDE]


def test_bad_input_is_rejected():
    with pytest.raises(ValueError):
        judge([100, 200, 150])
    with pytest.raises(ValueError):
        judge([100, 200, 210, 220])


def test_handbook_draws_without_external_resources():
    page = handbook()
    assert page.count("<svg") == 15 and "http" not in page
