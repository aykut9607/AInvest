"""Synthetic-profile evaluation of the Financial IQ rules (scoring v2; report sections 3.1.2, 3.2.3 and 3.4.2).

    py -3 evaluation/run_evaluation.py                # 300 profiles, seed 42
    py -3 evaluation/run_evaluation.py --n 600 --seed 7
    py -3 evaluation/run_evaluation.py --scorer <path to another FinancialIQ.BatchScorer project>

Scoring is done by the production rules (FinancialIqCommandManager.CalculateScore) through the
FinancialIQ.BatchScorer tool, never by a Python copy. Standard library only.

Steps
 1. generate clean profiles from three archetypes (strong / average / fragile finances)
 2. score them with the production rules
 3. copy, inject missing and erroneous values, and repair the copy two ways:
      naive  : missing -> 0, nothing else
      cleaned: the report's method (missing -> dataset median, "expenses far above income with no debt" ->
               debt re-derived)
 4. measure
    (a) reproducibility: the same input scored twice gives the same result
        monotonicity: making one input more favourable (other inputs fixed) must not lower the score
        separation: which segment each archetype lands in
    (b) robustness to dirty data: how close the naive and the cleaned repair get to the score of the clean record

Scoring v1 had a 6th factor comparing the self-reported risk with the finances, and (b) measured how well that
mismatch was detected. v2 removed the self-reported risk (it also caused the monotonicity violations v1 showed),
so (b) now measures the data-cleaning step instead.
"""

import argparse
import json
import random
import statistics
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCORER = ROOT / "services" / "financial-iq-service" / "src" / "FinancialIQ.BatchScorer"
OUT = Path(__file__).resolve().parent / "out"

# ranges as shares of the monthly income (debt, expense) and months of expenses (reserve)
ARCHETYPES = {
    "strong": {"reserve": (6, 14), "debt": (0.0, 0.18), "expense": (0.30, 0.55), "impatience": [1, 1, 2, 2, 3]},
    "average": {"reserve": (2.5, 7), "debt": (0.08, 0.32), "expense": (0.45, 0.72), "impatience": [2, 3, 3, 4]},
    "fragile": {"reserve": (0, 3.5), "debt": (0.25, 0.55), "expense": (0.55, 0.95), "impatience": [3, 4, 4, 5, 5]},
}
CORRUPTIBLE = ["monthlyExpenses", "monthlyDebtPayment", "cashReserve"]

# one favourable change at a time, every other input fixed
FAVOURABLE_CHANGES = {
    "cashReserve +20%": lambda p: p.update(cashReserve=round(p["cashReserve"] * 1.2, 2)),
    "monthlyExpenses -10%": lambda p: p.update(monthlyExpenses=round(p["monthlyExpenses"] * 0.9, 2)),
    "monthlyDebtPayment -20%": lambda p: p.update(monthlyDebtPayment=round(p["monthlyDebtPayment"] * 0.8, 2)),
    "totalDebt -20%": lambda p: p.update(totalDebt=round(p["totalDebt"] * 0.8, 2)),
    "investmentAmount +20%": lambda p: p.update(investmentAmount=round(p["investmentAmount"] * 1.2, 2)),
    "impatienceLevel -1": lambda p: p.update(impatienceLevel=max(1, p["impatienceLevel"] - 1)),
}


def generate(n: int, rng: random.Random) -> list[dict]:
    profiles = []
    kinds = list(ARCHETYPES)
    for i in range(n):
        kind = kinds[i % len(kinds)]
        a = ARCHETYPES[kind]
        income = round(rng.uniform(17_000, 150_000), -2)
        expenses = round(income * rng.uniform(*a["expense"]), -1)
        debt_payment = round(income * rng.uniform(*a["debt"]), -1)
        profiles.append({
            "userId": f"synth-{i:04d}",
            "archetype": kind,
            "monthlyIncome": income,
            "monthlyExpenses": expenses,
            "monthlyDebtPayment": debt_payment,
            "cashReserve": round(expenses * rng.uniform(*a["reserve"]), -2),
            "totalDebt": round(debt_payment * rng.uniform(6, 48), -2),
            "investmentAmount": round(income * rng.uniform(0, 4), -2),
            "impatienceLevel": rng.choice(a["impatience"]),
        })
    return profiles


def scorer_label(path: Path) -> str:
    """The scorer path as written to results.json: repo-relative, so no personal directory ends up in the repo."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return "external: " + path.name  # a copy outside the repo (e.g. another branch's checkout)


def build_scorer() -> None:
    subprocess.run(["dotnet", "build", str(SCORER), "-c", "Release", "-v", "quiet", "-nologo"], check=True)


def score(profiles: list[dict], name: str) -> dict[str, dict]:
    """Runs the production rules over the profiles; returns userId -> {score, segment, factorBreakdown}."""
    src, dst = OUT / f"{name}.in.json", OUT / f"{name}.scored.json"
    src.write_text(json.dumps(profiles, ensure_ascii=False, indent=1), encoding="utf-8")
    subprocess.run(
        ["dotnet", "run", "--project", str(SCORER), "-c", "Release", "--no-build", "--", str(src), str(dst)],
        check=True, capture_output=True,
    )
    return {r["userId"]: r for r in json.loads(dst.read_text(encoding="utf-8"))}


def corrupt(profiles: list[dict], rng: random.Random, missing_rate: float, error_rate: float) -> tuple[list[dict], Counter]:
    log: Counter = Counter()
    corrupted = []
    for p in profiles:
        q = dict(p)
        for field in CORRUPTIBLE:
            if rng.random() < missing_rate:
                q[field] = None
                log["missing values"] += 1
        if rng.random() < error_rate:
            # the error the report names: spending far above income while no debt is shown
            q["monthlyExpenses"] = round(q["monthlyIncome"] * rng.uniform(1.5, 3), -1)
            q["monthlyDebtPayment"] = 0
            log["erroneous records"] += 1
        corrupted.append(q)
    return corrupted, log


def repair_naive(profiles: list[dict]) -> list[dict]:
    # what happens without a cleaning step: a missing amount is read as 0
    return [{k: (0 if v is None and k in CORRUPTIBLE else v) for k, v in p.items()} for p in profiles]


def repair_cleaned(profiles: list[dict]) -> tuple[list[dict], Counter]:
    log: Counter = Counter()
    repaired = [dict(p) for p in profiles]
    # overall median, not per segment: the segment comes from the score, so a per-segment fill would leak the result
    medians = {f: statistics.median(p[f] for p in repaired if p[f] is not None) for f in CORRUPTIBLE}
    for p in repaired:
        for field in CORRUPTIBLE:
            if p[field] is None:
                p[field] = medians[field]
                log["filled with median"] += 1
        if p["monthlyExpenses"] > 1.2 * p["monthlyIncome"] and p["monthlyDebtPayment"] == 0:
            # spending above income must be financed somehow: re-derive the debt payment from the gap
            p["monthlyDebtPayment"] = round(p["monthlyExpenses"] - p["monthlyIncome"], -1)
            log["debt re-derived"] += 1
    return repaired, log


def reproducibility(profiles: list[dict]) -> dict:
    first, second = score(profiles, "repro_a"), score(profiles, "repro_b")
    same = sum(first[k]["score"] == second[k]["score"] and first[k]["factorBreakdown"] == second[k]["factorBreakdown"]
               for k in first)
    return {"profiles": len(first), "identical": same, "rate": same / len(first)}


def monotonicity(profiles: list[dict], base: dict) -> dict:
    variants = []
    for p in profiles:
        for change, apply in FAVOURABLE_CHANGES.items():
            v = dict(p)
            apply(v)
            v["userId"] = f"{p['userId']}|{change}"
            variants.append(v)
    scored = score(variants, "monotonicity")

    per_change: dict[str, Counter] = {c: Counter() for c in FAVOURABLE_CHANGES}
    examples = []
    for key, after in scored.items():
        user, change = key.split("|")
        before = base[user]
        per_change[change]["checked"] += 1
        if after["score"] < before["score"]:
            per_change[change]["score dropped"] += 1
            lost = [f for f, pts in after["factorBreakdown"]["factors"].items()
                    if pts < before["factorBreakdown"]["factors"][f]]
            if len(examples) < 5:
                examples.append({"userId": user, "change": change, "before": before["score"],
                                 "after": after["score"], "factorsLost": lost})
    checked = sum(c["checked"] for c in per_change.values())
    dropped = sum(c["score dropped"] for c in per_change.values())
    return {"checked": checked, "scoreDropped": dropped,
            "perChange": {c: dict(cnt) for c, cnt in per_change.items()}, "examples": examples}


def agreement(clean: dict, repaired: dict, corrupted_ids: set[str]) -> dict:
    """How close the repaired records get to the clean truth, over all records and over the touched ones only."""
    def stats(ids):
        diffs = [abs(clean[k]["score"] - repaired[k]["score"]) for k in ids]
        same_segment = sum(clean[k]["segment"] == repaired[k]["segment"] for k in ids)
        return {"records": len(ids), "sameSegment": same_segment,
                "sameSegmentRate": round(same_segment / len(ids), 3) if ids else None,
                "meanAbsScoreDiff": round(statistics.mean(diffs), 2) if diffs else None,
                "maxAbsScoreDiff": max(diffs) if diffs else None}
    return {"all": stats(list(clean)), "corruptedOnly": stats(sorted(corrupted_ids))}


def main() -> None:
    global SCORER
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--missing-rate", type=float, default=0.08)
    ap.add_argument("--error-rate", type=float, default=0.05)
    ap.add_argument("--scorer", type=Path, default=SCORER, help="FinancialIQ.BatchScorer project to score with")
    args = ap.parse_args()
    SCORER = args.scorer

    OUT.mkdir(exist_ok=True)
    rng = random.Random(args.seed)
    build_scorer()

    profiles = generate(args.n, rng)
    clean_scored = score(profiles, "clean")

    corrupted, corruption_log = corrupt(profiles, rng, args.missing_rate, args.error_rate)
    corrupted_ids = {c["userId"] for c, p in zip(corrupted, profiles) if c != p}
    cleaned, cleaning_log = repair_cleaned(corrupted)
    naive_scored = score(repair_naive(corrupted), "corrupted_naive")
    cleaned_scored = score(cleaned, "corrupted_cleaned")

    versions = Counter(r["factorBreakdown"].get("version", "v1") for r in clean_scored.values())
    results = {
        "parameters": {**vars(args), "scorer": scorer_label(args.scorer)},
        "scoringVersion": dict(versions),
        "segments": dict(Counter(r["segment"] for r in clean_scored.values())),
        "archetypeVsSegment": {f"{a}->{s}": c for (a, s), c in sorted(
            Counter((p["archetype"], clean_scored[p["userId"]]["segment"]) for p in profiles).items())},
        "appliedRules": dict(Counter(str(r["factorBreakdown"].get("appliedRule")) for r in clean_scored.values())),
        "a_reproducibility": reproducibility(profiles),
        "a_monotonicity": monotonicity(profiles, clean_scored),
        "b_dirtyData": {
            "corruption": dict(corruption_log),
            "cleaning": dict(cleaning_log),
            "naiveRepair": agreement(clean_scored, naive_scored, corrupted_ids),
            "reportCleaning": agreement(clean_scored, cleaned_scored, corrupted_ids),
        },
    }
    (OUT / "results.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
