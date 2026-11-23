from signals.patterns.elliott import DIAGONAL, DOWN, EXT_3RD, IMPULSE, UP, ZIGZAG, abc_counts, impulse_counts
from signals.patterns.fib import Level, cluster, fit_to_range, fit_to_targets, in_range, near
from signals.patterns.harmonic import BEARISH, BULLISH, complete_patterns, developing_patterns
from signals.structure.pivots import HIGH, LOW
from signals.structure.zigzag import SwingPoint


def swings(prices, start_kind=LOW):
    """Alternating swing points 10 bars apart, each confirmed 3 bars later."""
    kinds = [start_kind, HIGH if start_kind == LOW else LOW]
    return [SwingPoint(kinds[i % 2], 10 * i, float(p), 10 * i + 3) for i, p in enumerate(prices)]


# ---------- fib helpers ----------

def test_three_percent_tolerance():
    assert near(0.80, 0.786) and not near(0.82, 0.786)
    assert in_range(0.371, 0.382, 0.5) and not in_range(0.36, 0.382, 0.5)    # 0.382 x 0.97 = 0.3705
    assert fit_to_targets(0.618, [0.618]) == 1.0 and fit_to_targets(0.9, [0.618]) == 0.0
    assert fit_to_range(0.3, 0.236, 0.382) == 1.0


def test_cluster_takes_the_densest_group():
    zone = cluster([Level("a", 100), Level("b", 102), Level("c", 103), Level("d", 130)], width=5)
    assert (zone.low, zone.high) == (100, 103)


# ---------- Elliott impulses ----------
# 0=100, 1=120 (w1 20), 2=110 (r2 0.5), 3=142.36 (w3 32.36 = 1.618 x w1), 4=130 (r4 0.382)
TEXTBOOK = [100, 120, 110, 142.36, 130]


def test_textbook_0_to_4_passes_and_gets_a_wave5_zone_above_wave3():
    [count] = [c for c in impulse_counts(swings(TEXTBOOK)) if len(c.points) == 5]

    assert (count.direction, count.kind, count.extension) == (UP, IMPULSE, EXT_3RD)
    assert count.fit > 90
    zone = count.wave5_zone
    names = {m.name for m in zone.members}
    # 2-3-4 ext 0.618 = 130 + 20 = 150 and [5]=[1] = 150 coincide: the densest group
    assert {"2-3-4 ext 0.618", "[5]=[1]"} <= names
    assert zone.low <= 150 <= zone.high
    assert count.key_level == 130 and count.invalidation > zone.high
    assert count.known_at == 43


def test_wave2_beyond_the_start_breaks_rule_1():
    assert [c for c in impulse_counts(swings([100, 120, 99, 140, 130])) if len(c.points) == 5] == []


def test_wave4_into_wave1_is_only_a_contracting_diagonal():
    # w1 30, w3 20 (< w1), wave 4 at 120 is below wave 1's top 130: contracting diagonal
    [diag] = [c for c in impulse_counts(swings([100, 130, 110, 130.5, 120])) if len(c.points) == 5]
    assert diag.kind == DIAGONAL
    # a wave 3 longer than wave 1 with overlap is no diagonal -> dropped
    assert [c for c in impulse_counts(swings([100, 120, 110, 150, 118])) if len(c.points) == 5] == []


def test_wave3_shortest_breaks_rule_2_in_a_complete_count():
    # w1 20, w3 12 (shortest), w5 25
    assert [c for c in impulse_counts(swings([100, 120, 110, 122.5, 121, 146])) if len(c.points) == 6] == []


def test_wave3_shorter_than_wave1_caps_wave5():
    [count] = [c for c in impulse_counts(swings([100, 130, 115, 140, 132])) if len(c.points) == 5]   # w1 30, w3 25
    assert all(m.price <= 132 + 25 for m in count.wave5_zone.members)


def test_falling_impulse_is_the_mirror():
    mirrored = [200 - p for p in TEXTBOOK]
    [count] = [c for c in impulse_counts(swings(mirrored, start_kind=HIGH)) if len(c.points) == 5]
    assert count.direction == DOWN
    assert count.wave5_zone.low <= 50 <= count.wave5_zone.high      # 200 - 150
    assert count.invalidation < count.wave5_zone.low


# ---------- Elliott corrections ----------

def test_zigzag_abc_and_c_zone():
    # S 200 (top), A 180 (drop 20), B 190 (0.5 back): C zone around 170 (= A) and 157.6 (1.618 A)
    counts = [c for c in abc_counts(swings([200, 180, 190], start_kind=HIGH)) if c.kind == ZIGZAG]
    assert counts and counts[0].direction == DOWN
    assert any(abs(m.price - 170) < 1e-9 for m in counts[0].c_zone.members)


def test_b_at_0786_is_not_a_zigzag():
    assert [c for c in abc_counts(swings([200, 180, 196], start_kind=HIGH)) if c.kind == ZIGZAG] == []


# ---------- harmonic ----------

def test_bullish_gartley_complete():
    # X 100, A 200 (XA 100), B 138.2 (0.618), C 186.8 (0.786 of AB), D 121.4 (0.786 of XA):
    # CD 65.4 = 1.06 x AB (AB=CD) and 1.35 x BC
    [p] = complete_patterns(swings([100, 200, 138.2, 186.8, 121.4]))
    assert (p.name, p.direction) == ("Gartley", BULLISH)
    assert p.invalidation == 100.0                    # beyond X
    assert round(p.target, 1) == round(121.4 + 0.382 * (200 - 121.4), 1)


def test_developing_bat_projects_a_prz_at_0886():
    # X 100, A 200, B 155 (0.45), C 185 (0.667 of AB): D expected at 200 - 0.886 x 100 = 111.4
    [bat] = [p for p in developing_patterns(swings([100, 200, 155, 185])) if p.name == "Bat"]
    assert bat.prz.low <= 111.4 <= bat.prz.high
    assert round(bat.invalidation, 1) == 87.0         # 1.13 XA
    assert bat.direction == BULLISH


def test_bearish_butterfly_is_the_mirror():
    # X 200, A 100, B 178.6 (0.786), C 130 (0.62 of AB), D 227 (1.27 XA beyond X)
    found = {p.name for p in complete_patterns(swings([200, 100, 178.6, 130, 227], start_kind=HIGH))}
    assert "Butterfly" in found
    assert all(p.direction == BEARISH for p in complete_patterns(swings([200, 100, 178.6, 130, 227], start_kind=HIGH)))


def test_cd_shorter_than_ab_is_no_pattern():
    # same Gartley ratios but C only 0.618 of AB: CD = 0.89 x AB < AB
    assert complete_patterns(swings([100, 200, 138.2, 176.4, 121.4])) == []


def test_c_outside_0382_0886_is_no_pattern():
    assert complete_patterns(swings([100, 200, 138.2, 195, 121.4])) == []     # C = 0.92 of AB
