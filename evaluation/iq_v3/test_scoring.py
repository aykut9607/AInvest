"""Unit tests for the v3 scoring prototype (stdlib unittest).

    cd evaluation
    py -3 -m unittest discover -s iq_v3 -t . -v
"""

import json
import random
import unittest
from decimal import Decimal
from pathlib import Path

from iq_v3 import population as pop
from iq_v3 import scoring as v3

GOLDEN = Path(__file__).resolve().parent.parent / "out" / "iq_v3_golden.json"
MONEY = ["monthlyIncome", "monthlyExpenses", "monthlyDebtPayment", "totalDebt", "cashReserve", "investmentAmount"]
FAVOURABLE_UP = {"monthlyIncome", "cashReserve", "investmentAmount"}

# a factor's warnings (any of them explains points below 60 %)
RELATED = {
    "CashReserveMonths": {v3.W_LOW_RESERVE},
    "DebtToIncomeRatio": {v3.W_HIGH_DEBT_BURDEN, v3.W_ELEVATED_DEBT_BURDEN, v3.W_HIGH_TOTAL_DEBT,
                          v3.W_ELEVATED_TOTAL_DEBT},
    "InstallmentToIncome": {v3.W_HIGH_DEBT_BURDEN, v3.W_ELEVATED_DEBT_BURDEN},
    "NetDebtToIncome": {v3.W_HIGH_TOTAL_DEBT, v3.W_ELEVATED_TOTAL_DEBT},
    "SavingsRate": {v3.W_NEGATIVE_SAVINGS, v3.W_LOW_SAVINGS},
    "ExpenseRatio": {v3.W_OVERSPENDING, v3.W_HIGH_EXPENSE_RATIO},
    "Impatience": {v3.W_HIGH_IMPATIENCE},
}


def sample(n=300, seed=3) -> list[dict]:
    rng = random.Random(seed)
    return pop.core(n, rng) + pop.stress(40, rng) + pop.demos()


class RoundingAndInterpolation(unittest.TestCase):
    def test_round_half_up_two_steps(self):
        self.assertEqual(v3.round_points(Decimal("2.5")), 3)
        self.assertEqual(v3.round_points(Decimal("12.5")), 13)  # not banker's rounding (would give 12)
        self.assertEqual(v3.round_points(Decimal("2.4999995")), 3)  # 6-decimal step first: 2.500000
        self.assertEqual(v3.round_points(Decimal("2.4999994")), 2)
        self.assertEqual(v3.round_points(Decimal("2.4999999999999999999999999995")), 3)  # division noise
        self.assertEqual(v3.round_points(Decimal(0)), 0)

    def test_interpolate_clamps_and_is_linear(self):
        t = v3.RESERVE_MONTHS
        self.assertEqual(v3.interpolate(Decimal(-1), t), 0)
        self.assertEqual(v3.interpolate(Decimal("1.5"), t), Decimal("0.3"))
        self.assertEqual(v3.interpolate(Decimal(3), t), Decimal("0.6"))
        self.assertEqual(v3.interpolate(Decimal("4.5"), t), Decimal("0.8"))
        self.assertEqual(v3.interpolate(Decimal(99), t), 1)
        # decreasing table
        self.assertEqual(v3.interpolate(Decimal("0.15"), v3.INSTALLMENT_RATIO), Decimal("0.8"))
        self.assertEqual(v3.interpolate(Decimal("0.05"), v3.INSTALLMENT_RATIO), 1)

    def test_anchor_ladder(self):
        # every factor table runs between 0 and 1 and passes 0.6 (the warning line)
        for table in (v3.RESERVE_MONTHS, v3.INSTALLMENT_RATIO, v3.NET_DEBT_YEARS, v3.SAVINGS_RATE,
                      v3.EXPENSE_RATIO, v3.IMPATIENCE):
            shares = [s for _, s in table]
            self.assertEqual({min(shares), max(shares)}, {Decimal(0), Decimal(1)})
            self.assertIn(Decimal("0.6"), shares)
            xs = [x for x, _ in table]
            self.assertEqual(xs, sorted(xs))


class Invariants(unittest.TestCase):
    def test_points_add_up_and_stay_in_range(self):
        for p in sample():
            for name, variant in v3.VARIANTS.items():
                r = v3.score(p, name)
                b = r["factorBreakdown"]
                self.assertEqual(sum(b["factors"].values()), r["score"], (name, p["userId"]))
                self.assertEqual(b["factorMaximums"], variant.maxima)
                self.assertEqual(sum(b["factorMaximums"].values()), 100)
                for f, pts in b["factors"].items():
                    self.assertTrue(0 <= pts <= variant.maxima[f], (name, f, pts))
                self.assertEqual(r["segment"], v3.segment(r["score"]))
                self.assertEqual(b["version"], "v3")

    def test_monotone_in_every_input(self):
        for original in sample(150, seed=11):
            for f in MONEY + ["impatienceLevel"]:
                p = original
                if f == "impatienceLevel":
                    changes = [(p[f] - 1, True), (p[f] + 1, False)]
                    changes = [(k, fav) for k, fav in changes if 1 <= k <= 5]
                else:
                    if not p[f]:
                        p = dict(p, **{f: 1000.0})  # move a zero input away from 0 so both directions exist
                    x = p[f]
                    changes = [(round(x * 1.3, 2), f in FAVOURABLE_UP), (round(x * 0.7, 2), f not in FAVOURABLE_UP)]
                for value, favourable in changes:
                    q = dict(p, **{f: value})
                    # the expense floor ties the reserve to the income: skip income changes inside the floor
                    if f == "monthlyIncome" and max(p["monthlyExpenses"], q["monthlyExpenses"]) < 0.1 * value:
                        continue
                    for name in v3.VARIANTS:
                        before, after = v3.score(p, name)["score"], v3.score(q, name)["score"]
                        if favourable:
                            self.assertGreaterEqual(after, before, (name, p["userId"], f, value))
                        else:
                            self.assertLessEqual(after, before, (name, p["userId"], f, value))

    def test_scale_free(self):
        # no TL thresholds: the same finances at 30 % higher prices score exactly the same (audit G12)
        for p in sample(100, seed=5):
            q = dict(p, **{f: round(p[f] * 1.3, 4) for f in MONEY})
            for name in v3.VARIANTS:
                self.assertEqual(v3.score(p, name)["factorBreakdown"], v3.score(q, name)["factorBreakdown"])

    def test_one_tl_never_moves_the_score_by_more_than_one(self):
        for uid, at, past in pop.threshold_probes():
            for name in v3.VARIANTS:
                self.assertLessEqual(abs(v3.score(past, name)["score"] - v3.score(at, name)["score"]), 1, (uid, name))
        for uid, _, before, after in pop.regression_probes():
            if after is not None and uid != "G4" and not uid.startswith("G5"):
                for name in v3.VARIANTS:
                    self.assertLessEqual(abs(v3.score(after, name)["score"] - v3.score(before, name)["score"]), 1,
                                         (uid, name))

    def test_income_must_be_positive(self):
        with self.assertRaises(ValueError):
            v3.score(pop.profile("x", 0, 1000))


class Warnings(unittest.TestCase):
    def test_a_factor_below_60_percent_always_has_its_warning(self):
        for p in sample():
            m = v3.measures(p)
            for name, variant in v3.VARIANTS.items():
                b = v3.score(p, name)["factorBreakdown"]
                ws = set(b["warnings"])
                self.assertTrue(ws <= set(v3.FACTOR_WARNINGS + v3.OTHER_WARNINGS), ws)
                self.assertEqual(len(b["warnings"]), len(ws))  # no duplicates
                if m.solvency_cap < 1:
                    self.assertIn(v3.W_EXTREME_DEBT, ws)
                    continue
                for f, pts in b["factors"].items():
                    weak = pts < 0.6 * variant.maxima[f]
                    self.assertEqual(weak, bool(ws & RELATED[f]), (name, p["userId"], f, pts, ws))

    def test_lowest_warning_free_score_is_at_least_60(self):
        for p in sample():
            for name in v3.VARIANTS:
                r = v3.score(p, name)
                if not r["factorBreakdown"]["warnings"]:
                    self.assertGreaterEqual(r["score"], 60)

    def test_v2_texts_keep_their_v2_threshold(self):
        low = v3.score(pop.profile("x", 30000, 25000, 7000, 90000, 3000, 10000, 5))["factorBreakdown"]["warnings"]
        self.assertIn(v3.W_NEGATIVE_SAVINGS, low)       # savings rate < 0
        self.assertIn(v3.W_OVERSPENDING, low)           # expenses > 80 % of income
        self.assertIn(v3.W_HIGH_IMPATIENCE, low)        # level 5
        # expenses 75 %, installment 20 %, savings 5 %
        mild = v3.score(pop.profile("y", 40000, 30000, 8000, 100000, 64000, 0, 3))["factorBreakdown"]["warnings"]
        self.assertIn(v3.W_HIGH_EXPENSE_RATIO, mild)    # weak, but not above 80 % ("overspending")
        self.assertIn(v3.W_LOW_SAVINGS, mild)           # weak, but not negative
        self.assertNotIn(v3.W_ELEVATED_DEBT_BURDEN, mild)  # exactly 20 %: 15 of 25 points, no warning
        self.assertNotIn(v3.W_HIGH_IMPATIENCE, mild)    # level 3 is the neutral answer

    def test_consistency_and_data_quality(self):
        ws = v3.score(pop.profile("a", 40000, 16000, 2000, 2000000, 50000, 0, 2))["factorBreakdown"]["warnings"]
        self.assertIn(v3.W_BELOW_INTEREST, ws)
        ws = v3.score(pop.profile("b", 50000, 30000, 8000, 0, 60000, 0, 3))["factorBreakdown"]["warnings"]
        self.assertIn(v3.W_INSTALLMENT_NO_DEBT, ws)
        ws = v3.score(pop.profile("c", 50000, 30000, 8000, 5000, 60000, 0, 3))["factorBreakdown"]["warnings"]
        self.assertIn(v3.W_INSTALLMENT_OVER_DEBT, ws)
        ws = v3.score(pop.profile("d", 50000, 0, 0, 0, 0.01, 0, 1))["factorBreakdown"]["warnings"]
        self.assertIn(v3.W_EXPENSES_TOO_LOW, ws)


class Labels(unittest.TestCase):
    def test_rule_labels(self):
        cases = {
            (40000, 16000, 4000, 120000000, 96000, 10000000, 1): (v3.RULE_SOLVENCY_CAP, 0),
            (40000, 16000, 4000, 50000000, 96000, 0, 1): (v3.RULE_SOLVENCY_CAP, 0),
            (30000, 29000, 0, 1000000, 2000000, 9000000, 5): (v3.RULE_WEALTH_RUNWAY, None),
            (20000, 8000, 2000, 0, 30000, 0, 2): (None, 88),
        }
        for vals, (rule, expected_score) in cases.items():
            for name in v3.VARIANTS:
                r = v3.score(pop.profile("x", *vals), name)
                self.assertEqual(r["factorBreakdown"]["appliedRule"], rule, (vals, name))
                if expected_score is not None and rule is not None:
                    self.assertEqual(r["score"], expected_score)
        self.assertEqual(v3.score(pop.profile("x", 20000, 8000, 2000, 0, 30000, 0, 2), "v3a")["score"], 88)

    def test_wealth_runway_label_needs_five_years(self):
        # 2 months of expenses in cash and a deficit: runway 2/12 year, no label
        short = pop.profile("s", 30000, 33000, 0, 0, 66000, 0, 3)
        # 2 months of outflow in cash, large installment: runway 0.42 years lifts a rounded point, still no label
        lifted = pop.profile("l", 30000, 20000, 30000, 0, 100000, 0, 3)
        # 30 years of expenses in cash and a deficit: the runway lifts savings to the maximum -> label
        rich = pop.profile("r", 30000, 33000, 0, 0, 30 * 12 * 33000, 0, 3)
        self.assertLess(v3.measures(lifted).runway_years, v3.WEALTH_RUNWAY_LABEL_MIN_YEARS)
        for name, variant in v3.VARIANTS.items():
            self.assertIsNone(v3.score(short, name)["factorBreakdown"]["appliedRule"], name)
            self.assertIsNone(v3.score(lifted, name)["factorBreakdown"]["appliedRule"], name)
            r = v3.score(rich, name)
            self.assertEqual(r["factorBreakdown"]["appliedRule"], v3.RULE_WEALTH_RUNWAY, name)
            self.assertEqual(r["factorBreakdown"]["factors"]["SavingsRate"], variant.maxima["SavingsRate"])
        # the lift itself is unchanged: v3c-i5 still gives the point (26, not the unlifted 25)
        self.assertEqual(v3.score(lifted, "v3c-i5")["score"], 26)

    def test_wealth_runway_label_implies_five_years_and_a_gain(self):
        for p in sample():
            m = v3.measures(p)
            for name, variant in v3.VARIANTS.items():
                r = v3.score(p, name)
                if r["factorBreakdown"]["appliedRule"] == v3.RULE_WEALTH_RUNWAY:
                    self.assertGreaterEqual(m.runway_years, v3.WEALTH_RUNWAY_LABEL_MIN_YEARS)
                    unlifted, _ = v3._shares(m, variant.layout, v3.ZERO)
                    self.assertGreater(r["score"], sum(v3._points(unlifted, variant.maxima, m.solvency_cap).values()))

    def test_cap_is_continuous(self):
        # net debt from 5 to 15 years of income: the score falls step by step, never jumps
        last = None
        for years in range(4, 17):
            r = v3.score(pop.profile("x", 40000, 16000, 12000, 480000 * years, 0, 0, 1), "v3a")
            if last is not None:
                self.assertLessEqual(r["score"], last)
                self.assertLessEqual(last - r["score"], 12)
            last = r["score"]
        self.assertEqual(last, 0)


class Golden(unittest.TestCase):
    @unittest.skipUnless(GOLDEN.exists(), "run evaluation/iq_eval_v3.py first")
    def test_golden_table_matches_the_prototype(self):
        rows = json.loads(GOLDEN.read_text(encoding="utf-8"))["profiles"]
        self.assertGreaterEqual(len(rows), 35)
        for row in rows:
            p = dict(row["input"], userId=row["id"])
            self.assertEqual(v3.intermediates(p), row["intermediates"], row["id"])
            for name in v3.VARIANTS:
                r = v3.score(p, name)
                b = r["factorBreakdown"]
                got = {"score": r["score"], "segment": r["segment"], "factors": b["factors"],
                       "warnings": b["warnings"], "appliedRule": b["appliedRule"]}
                self.assertEqual(got, row[name], (row["id"], name))


if __name__ == "__main__":
    unittest.main()
