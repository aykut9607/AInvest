"""Extended evaluation of the Financial IQ scoring: production v2 (C# rules via BatchScorer) vs the v3 prototypes.

    py -3 evaluation/iq_eval_v3.py                    # 2000 calibrated + 100 stress profiles, seed 42
    py -3 evaluation/iq_eval_v3.py --n 4000 --seed 7
    py -3 evaluation/iq_eval_v3.py --calibrate        # only the population vs Turkish shares table

v2 is never re-implemented here: every v2 score comes from FinancialIqCommandManager.CalculateScore through the
already built FinancialIQ.BatchScorer (Release). v3a / v3b (and the impatience-weight-5 variants) come from
evaluation/iq_v3/scoring.py. Standard library only.

Metrics
 1. jump: largest |score change| for a +-1 % change of one input (+1 TL when the input is 0), max and p99
 2. monotonicity: favourable and adverse single-input changes (+-1 %, +-20 %, 0 -> +1 TL, 0 -> +10 % of income,
    impatience +-1), income included; a violation is a favourable change that lowers the score or an adverse one
    that raises it
 3. gaming: impatience 5 -> 1, borrowing 3 months of expenses and holding it as cash (installment unchanged /
    installment of a 24-month loan at 3.5 %), under-reporting expenses by 10 %
 4. warnings: lowest score without any warning, most points a factor loses without a related warning
 5. Spearman rank correlation between the versions
 6. segment shares of the calibrated population next to the Findex / Eurostat fragility shares
 7. demo, audit (G1-G10) and threshold probes side by side

Writes out/iq_v3_results.json (summary), out/iq_v3_golden.json (golden table for the C# port) and the scorer
intermediates out/iq_v3_v2.in.json / out/iq_v3_v2.scored.json.

Since 25 Nov the BatchScorer runs the C# port of v3c-i5. The script reads the version the scorer writes: with a v2
scorer the v2 column is measured live; with a v3 scorer the output is compared with the Python v3c-i5 profile by
profile (csharpPortCheck) and the v2 column is taken from out/iq_v3_v2_frozen.json (the 24 Nov v2 measurements).
"""

import argparse
import json
import math
import random
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

import realism_check
from iq_v3 import population as pop
from iq_v3 import scoring as v3

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(__file__).resolve().parent / "out"
DLL = (ROOT / "services" / "financial-iq-service" / "src" / "FinancialIQ.BatchScorer" / "bin" / "Release" / "net10.0"
       / "FinancialIQ.BatchScorer.dll")

MONEY = ["monthlyIncome", "monthlyExpenses", "monthlyDebtPayment", "totalDebt", "cashReserve", "investmentAmount"]
# +1 = a higher value is favourable
DIRECTION = {"monthlyIncome": 1, "monthlyExpenses": -1, "monthlyDebtPayment": -1, "totalDebt": -1,
             "cashReserve": 1, "investmentAmount": 1, "impatienceLevel": -1}
V3 = ["v3a", "v3b", "v3c", "v3a-i5", "v3b-i5", "v3c-i5"]
VERSIONS = ["v2"] + V3          # versions measured live; without a v2 scorer this becomes V3 (see main)
FROZEN_V2 = OUT / "iq_v3_v2_frozen.json"

# warnings that explain lost points of a factor (v2 texts, v3 texts); the cap / EXTREME_DEBT warning explains all
RELATED = {
    "CashReserveMonths": {"Low cash reserve"},
    "DebtToIncomeRatio": {"High debt burden", "High total debt", "Elevated debt burden", "Elevated total debt"},
    "InstallmentToIncome": {"High debt burden", "Elevated debt burden"},
    "NetDebtToIncome": {"High total debt", "Elevated total debt"},
    "SavingsRate": {"Negative savings rate", "Low savings rate"},
    "ExpenseRatio": {"Overspending relative to income", "High expense ratio"},
    "Impatience": {"High impatience"},
}
V2_MAXIMA = {"CashReserveMonths": 25, "DebtToIncomeRatio": 25, "SavingsRate": 25, "ExpenseRatio": 15, "Impatience": 10}


# --- scoring -----------------------------------------------------------------------------------------------------------
def clean_input(p: dict) -> dict:
    return {k: p[k] for k in ["userId"] + MONEY + ["impatienceLevel"]}


def score_batch(profiles: list[dict]) -> tuple[str, dict[str, dict]]:
    """Runs the BatchScorer (production C# rules); returns (scoring version it wrote, userId -> result)."""
    if not DLL.exists():
        sys.exit(f"BatchScorer not built: {DLL} (build it in Release first; this script does not build)")
    src, dst = OUT / "iq_v3_v2.in.json", OUT / "iq_v3_v2.scored.json"
    src.write_text(json.dumps([clean_input(p) for p in profiles], ensure_ascii=False), encoding="utf-8")
    run = subprocess.run(["dotnet", str(DLL), str(src), str(dst)], capture_output=True, text=True)
    if run.returncode != 0:
        sys.exit(f"BatchScorer failed: {run.stderr[:500]}")
    out, versions = {}, set()
    for r in json.loads(dst.read_text(encoding="utf-8")):
        b = r["factorBreakdown"]
        versions.add(b.get("version", "v1"))
        out[r["userId"]] = {"score": r["score"], "segment": r["segment"],
                            "factors": b["factors"], "warnings": b["warnings"], "appliedRule": b.get("appliedRule"),
                            "maxima": b.get("factorMaximums") or V2_MAXIMA}
    if len(versions) != 1:
        sys.exit(f"BatchScorer wrote mixed scoring versions: {sorted(versions)}")
    return versions.pop(), out


def score_v3(profiles: list[dict], variant: str) -> dict[str, dict]:
    out = {}
    for p in profiles:
        r = v3.score(p, variant)
        b = r["factorBreakdown"]
        out[p["userId"]] = {"score": r["score"], "segment": r["segment"], "factors": b["factors"],
                            "warnings": b["warnings"], "appliedRule": b["appliedRule"], "maxima": b["factorMaximums"]}
    return out


def score_all(profiles: list[dict]) -> tuple[str, dict[str, dict[str, dict]]]:
    version, batch = score_batch(profiles)
    res = {"v2" if version == "v2" else "csharp": batch}
    for v in V3:
        res[v] = score_v3(profiles, v)
    return version, res


def port_check(scores: dict) -> dict:
    """C# port (BatchScorer) vs the Python prototype, profile by profile, for the variant the port implements."""
    csharp = scores["csharp"]
    maxima = next(iter(csharp.values()))["maxima"]
    variant = next((k for k, v in v3.VARIANTS.items() if v.maxima == maxima), None)
    if variant is None:
        return {"variant": None, "note": f"factor maxima {maxima} match no prototype variant"}
    py = scores[variant]
    mismatch, examples = Counter(), defaultdict(list)
    for uid, c in csharp.items():
        for k in ("score", "segment", "factors", "warnings", "appliedRule"):
            if c[k] != py[uid][k]:
                mismatch[k] += 1
                if len(examples[k]) < 10:
                    examples[k].append({"userId": uid, "csharp": c[k], "python": py[uid][k]})
    return {"variant": variant, "profiles": len(csharp), "notScoredByCsharp": len(py) - len(csharp),
            "mismatches": {k: mismatch[k] for k in ("score", "segment", "factors", "warnings", "appliedRule")},
            "examples": dict(examples)}


def merge_frozen_v2(results: dict) -> None:
    """Puts the 24 Nov v2 measurements in as the v2 column (rows added since then get None)."""
    fz = json.loads(FROZEN_V2.read_text(encoding="utf-8"))
    for sec, value in fz["sections"].items():
        results[sec] = {"v2": value, **results[sec]}
    results["rankCorrelation"] = {**fz["rankCorrelation"], **results["rankCorrelation"]}
    for row in results["demos"]:
        row["v2"] = fz["rows"]["demos"].get(row["userId"])
    for row in results["regressionProbes"]:
        row["v2"] = fz["rows"]["regressionProbes"].get(row["id"])
    for row in results["thresholdProbes"]["rows"]:
        row["v2"] = fz["rows"]["thresholdProbes"].get(row["id"])
    results["thresholdProbes"]["maxAbsJump"]["v2"] = fz["thresholdMaxAbsJump"]
    results["parameters"]["v2Column"] = "frozen: " + FROZEN_V2.name + " (24 Nov 2026, pre-port BatchScorer)"


# --- perturbations -----------------------------------------------------------------------------------------------------
def perturbations(p: dict) -> list[tuple[str, str, int, bool, dict]]:
    """(input, label, direction of the change (+1 favourable / -1 adverse), counts for the 1 % jump metric, profile)."""
    out = []
    for f in MONEY:
        x = p[f]
        changes = []
        if x > 0:
            changes += [("x1.01", x * 1.01, True), ("x0.99", x * 0.99, True), ("x1.2", x * 1.2, False),
                        ("x0.8", x * 0.8, False)]
        else:
            changes += [("+1", 1.0, True), ("+10%inc", 0.1 * p["monthlyIncome"], False)]
        for label, value, jump in changes:
            value = round(value, 2)
            if value == x or (f == "monthlyIncome" and value <= 0):
                continue
            q = dict(p)
            q[f] = value
            fav = 1 if (value > x) == (DIRECTION[f] > 0) else -1
            q["userId"] = f"{p['userId']}|{f}|{label}"
            out.append((f, label, fav, jump, q))
    for step in (-1, 1):
        k = p["impatienceLevel"] + step
        if 1 <= k <= 5:
            q = dict(p, impatienceLevel=k, userId=f"{p['userId']}|impatienceLevel|{step:+d}")
            out.append(("impatienceLevel", f"{step:+d}", 1 if step < 0 else -1, False, q))
    return out


def gaming_variants(p: dict) -> list[tuple[str, dict]]:
    x = round(3 * max(p["monthlyExpenses"], 0.1 * p["monthlyIncome"]), 2)
    loan = dict(p, totalDebt=round(p["totalDebt"] + x, 2), cashReserve=round(p["cashReserve"] + x, 2))
    loan_paid = dict(loan, monthlyDebtPayment=round(p["monthlyDebtPayment"] + pop.annuity_payment(x, 0.035, 24), 2))
    return [
        ("impatience5", dict(p, impatienceLevel=5)),
        ("impatience1", dict(p, impatienceLevel=1)),
        ("borrowCashSamePayment", loan),
        ("borrowCashWithPayment", loan_paid),
        ("underreportExpenses10", dict(p, monthlyExpenses=round(p["monthlyExpenses"] * 0.9, 2))),
    ]


# --- statistics --------------------------------------------------------------------------------------------------------
def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0
    s = sorted(values)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def ranks(xs: list[float]) -> list[float]:
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a: list[float], b: list[float]) -> float:
    ra, rb = ranks(a), ranks(b)
    n = len(a)
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va = math.sqrt(sum((x - ma) ** 2 for x in ra))
    vb = math.sqrt(sum((y - mb) ** 2 for y in rb))
    return round(cov / (va * vb), 4) if va and vb else float("nan")


def shares(counter: Counter, n: int) -> dict[str, float]:
    return {k: round(v / n, 3) for k, v in sorted(counter.items())}


def finhealth(score: int) -> str:
    return "healthy (>=80)" if score >= 80 else "coping (40-79)" if score >= 40 else "vulnerable (<40)"


def is_data_quality(w: str) -> bool:
    return w in v3.DATA_QUALITY_WARNINGS


# --- metrics -----------------------------------------------------------------------------------------------------------
def jump_and_monotonicity(bases: list[dict], scores: dict, perts: dict[str, list]) -> dict:
    result = {}
    for ver in VERSIONS:
        s = scores[ver]
        jumps, per_input_max = [], defaultdict(int)
        worst = None
        viol = Counter()
        checked = Counter()
        examples = []
        flagged_only = True
        for p in bases:
            base = s[p["userId"]]["score"]
            for f, label, fav, jump, q in perts[p["userId"]]:
                after = s[q["userId"]]["score"]
                d = after - base
                if jump:
                    jumps.append(abs(d))
                    if abs(d) > per_input_max[f]:
                        per_input_max[f] = abs(d)
                    if worst is None or abs(d) > worst["absDelta"]:
                        worst = {"userId": p["userId"], "input": f, "change": label, "before": base, "after": after,
                                 "absDelta": abs(d)}
                key = f"{f} {'favourable' if fav > 0 else 'adverse'}"
                checked[key] += 1
                if d * fav < 0:
                    viol[key] += 1
                    flagged = "Expenses look too low" in s[q["userId"]]["warnings"] or \
                              "Expenses look too low" in s[p["userId"]]["warnings"]
                    flagged_only = flagged_only and flagged
                    if len(examples) < 4:
                        examples.append({"userId": p["userId"], "input": f, "change": label, "before": base,
                                         "after": after})
        result[ver] = {
            "jump1pct": {"checked": len(jumps), "max": max(jumps), "p99": percentile(jumps, 0.99),
                         "p999": percentile(jumps, 0.999),
                         "mean": round(sum(jumps) / len(jumps), 3), "maxPerInput": dict(per_input_max),
                         "worst": worst},
            "monotonicity": {"checked": sum(checked.values()), "violations": sum(viol.values()),
                             "perChange": {k: {"checked": checked[k], "violations": viol[k]} for k in sorted(checked)},
                             "allViolationsFlaggedExpensesTooLow": flagged_only if viol else None,
                             "examples": examples},
        }
    return result


def gaming(core: list[dict], game_scores: dict) -> dict:
    out = {}
    for ver in VERSIONS:
        s = game_scores[ver]
        g = defaultdict(list)
        for p in core:
            uid = p["userId"]
            base = s[f"{uid}|base"]["score"]
            g["impatience5to1"].append(s[f"{uid}|impatience1"]["score"] - s[f"{uid}|impatience5"]["score"])
            g["borrowCashSamePayment"].append(s[f"{uid}|borrowCashSamePayment"]["score"] - base)
            g["borrowCashWithPayment"].append(s[f"{uid}|borrowCashWithPayment"]["score"] - base)
            g["underreportExpenses10"].append(s[f"{uid}|underreportExpenses10"]["score"] - base)
        out[ver] = {k: {"mean": round(sum(v) / len(v), 2), "p90": percentile(v, 0.9), "max": max(v),
                        "min": min(v)} for k, v in g.items()}
    return out


def warning_consistency(ids: list[str], scores: dict) -> dict:
    out = {}
    for ver in VERSIONS:
        s = scores[ver]
        strict, ignoring_dq = None, None
        lost = defaultdict(int)
        lost_example = {}
        for uid in ids:
            r = s[uid]
            ws = set(r["warnings"])
            if not ws and (strict is None or r["score"] < strict):
                strict = r["score"]
            if not {w for w in ws if not is_data_quality(w)} and (ignoring_dq is None or r["score"] < ignoring_dq):
                ignoring_dq = r["score"]
            if "Extreme total debt" in ws:
                continue
            for f, pts in r["factors"].items():
                miss = r["maxima"][f] - pts
                if miss > lost[f] and not (ws & RELATED[f]) and r["appliedRule"] is None:
                    lost[f] = miss
                    lost_example[f] = uid
        out[ver] = {"lowestScoreNoWarnings": strict, "lowestScoreNoFactorWarnings": ignoring_dq,
                    "maxFactorPointsLostWithoutWarning": dict(lost),
                    "maxFactorPointsLostWithoutWarningExample": lost_example}
    return out


def segments(core: list[dict], scores: dict) -> dict:
    n = len(core)
    out = {}
    for ver in VERSIONS:
        s = scores[ver]
        out[ver] = {"standard (41/71)": shares(Counter(s[p["userId"]]["segment"] for p in core), n),
                    "finhealth (40/80)": shares(Counter(finhealth(s[p["userId"]]["score"]) for p in core), n),
                    "meanScore": round(sum(s[p["userId"]]["score"] for p in core) / n, 1)}
    return out


def rank_correlations(core: list[dict], scores: dict) -> dict:
    vec = {ver: [scores[ver][p["userId"]]["score"] for p in core] for ver in VERSIONS}
    pairs = [("v2", "v3a"), ("v2", "v3b"), ("v2", "v3c"), ("v3a", "v3b"), ("v3a", "v3c"), ("v2", "v3a-i5"),
             ("v2", "v3c-i5"), ("v3a", "v3a-i5"), ("v3b", "v3b-i5"), ("v3c", "v3c-i5")]
    out = {f"{a}~{b}": spearman(vec[a], vec[b]) for a, b in pairs if a in vec and b in vec}
    # redundancy G7: expense points vs savings points
    for ver in [v for v in ("v2", "v3a") if v in vec]:
        out[f"{ver} ExpenseRatio~SavingsRate points"] = spearman(
            [scores[ver][p["userId"]]["factors"]["ExpenseRatio"] for p in core],
            [scores[ver][p["userId"]]["factors"]["SavingsRate"] for p in core])
    return out


def rules_by_stratum(profiles: list[dict], scores: dict) -> dict:
    out = {}
    for ver in VERSIONS:
        c = Counter((p["stratum"], str(scores[ver][p["userId"]]["appliedRule"])) for p in profiles)
        out[ver] = {f"{k[0]}:{k[1]}": v for k, v in sorted(c.items())}
    return out


def side_by_side(ids: list[str], scores: dict) -> list[dict]:
    rows = []
    for uid in ids:
        row = {"userId": uid}
        for ver in VERSIONS:
            r = scores[ver][uid]
            row[ver] = f"{r['score']} {r['segment']}" + (f" {r['appliedRule']}" if r["appliedRule"] else "")
        rows.append(row)
    return rows


def pair_table(pairs: list[tuple[str, str, dict, dict]], scores: dict) -> list[dict]:
    rows = []
    for uid, what, before, after in pairs:
        row = {"id": uid, "finding": what}
        for ver in VERSIONS:
            b = scores[ver][before["userId"]]
            row[ver] = f"{b['score']}" if after is None else f"{b['score']}->{scores[ver][after['userId']]['score']}"
        rows.append(row)
    return rows


def threshold_table(probes: list[tuple[str, dict, dict]], scores: dict) -> dict:
    rows, worst = [], {}
    for uid, at, past in probes:
        row = {"id": uid}
        for ver in VERSIONS:
            d = scores[ver][past["userId"]]["score"] - scores[ver][at["userId"]]["score"]
            row[ver] = d
            worst[ver] = max(worst.get(ver, 0), abs(d))
        rows.append(row)
    return {"maxAbsJump": worst, "rows": rows}


def diagnostics(core: list[dict]) -> dict:
    """How often each v3 mechanism is active in the calibrated population (shares of the core profiles)."""
    c = Counter()
    for p in core:
        m = v3.measures(p)
        _, own = v3._shares(m, "a", m.runway_share)
        c["interestFloorBinds"] += m.payment_eff > m.payment
        c["expenseFloorBinds"] += m.expenses_eff > m.expenses
        c["runwayShareAboveZero"] += m.runway_share > 0
        c["solvencyCapBelowOne"] += m.solvency_cap < 1
        c["netDebtShareFull"] += own["netDebt"] == 1
        c["v3aNetDebtPartBinds"] += own["netDebt"] < own["installment"]
        c["excessLiquidOffsetsDebt"] += m.excess_liquid > 0 and m.debt > 0
    return {k: round(v / len(core), 4) for k, v in sorted(c.items())}


def calibration(core: list[dict]) -> list[dict]:
    rows = realism_check.compare(core)
    return [{"key": r["key"], "label": r["label"], "turkey": r["turkey"], "synthetic": round(r["synthetic"], 4)
             if r["synthetic"] is not None else None, "unit": r["unit"], "fit": r["fit"]} for r in rows]


def print_calibration(rows: list[dict]) -> None:
    print("| Gösterge | Türkiye | Sentetik (çekirdek) |")
    print("|---|---|---|")
    for r in rows:
        print(f"| {r['label']} | {realism_check.fmt(r['turkey'], r['unit'])} "
              f"| {realism_check.fmt(r['synthetic'], r['unit'])} |")


# --- golden table ------------------------------------------------------------------------------------------------------
def golden(profiles: list[dict], v2_score) -> list[dict]:
    rows = []
    for p in profiles:
        row = {"id": p["userId"], "input": {k: p[k] for k in MONEY + ["impatienceLevel"]},
               "v2Score": v2_score(p["userId"]), "intermediates": v3.intermediates(p)}
        for ver in v3.VARIANTS:
            r = v3.score(p, ver)
            b = r["factorBreakdown"]
            row[ver] = {"score": r["score"], "segment": r["segment"], "factors": b["factors"],
                        "warnings": b["warnings"], "appliedRule": b["appliedRule"]}
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--n", type=int, default=2000, help="calibrated core profiles")
    ap.add_argument("--stress", type=int, default=100, help="stress profiles (rich, wealthy, extreme/hidden debt)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--calibrate", action="store_true", help="only print the calibration table")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    OUT.mkdir(exist_ok=True)

    rng = random.Random(args.seed)
    core = pop.core(args.n, rng)
    cal = calibration(core)
    if args.calibrate:
        print_calibration(cal)
        return
    stress = pop.stress(args.stress, rng)
    demos = pop.demos()
    regressions = pop.regression_probes()
    thresholds = pop.threshold_probes()

    probe_profiles = [b for _, _, b, _ in regressions] + [a for _, _, _, a in regressions if a] + \
                     [x for _, a, b in thresholds for x in (a, b)]
    bases = core + stress + demos + [b for _, _, b, _ in regressions] + [a for _, a, _ in thresholds]
    perts = {p["userId"]: perturbations(p) for p in bases}
    games = []
    for p in core:
        games.append(dict(p, userId=f"{p['userId']}|base"))
        games += [dict(q, userId=f"{p['userId']}|{name}") for name, q in gaming_variants(p)]

    everything = {p["userId"]: p for p in core + stress + demos + probe_profiles}
    for plist in perts.values():
        for *_, q in plist:
            everything[q["userId"]] = q
    for g in games:
        everything[g["userId"]] = g
    allp = list(everything.values())
    global VERSIONS
    print(f"scoring {len(allp)} profiles with the BatchScorer and {', '.join(V3)} ...", flush=True)
    scorer_version, scores = score_all(allp)
    live_v2 = scorer_version == "v2"
    if not live_v2:
        VERSIONS = list(V3)
        if not FROZEN_V2.exists():
            sys.exit(f"the BatchScorer runs {scorer_version}, not v2, and {FROZEN_V2.name} is missing")
        frozen_gold = json.loads(FROZEN_V2.read_text(encoding="utf-8"))["goldenV2Score"]
    print(f"BatchScorer scoring version: {scorer_version}", flush=True)

    golden_ids = ([d["userId"] for d in demos if d["userId"] != "demo-trend-1"]
                  + [b["userId"] for _, _, b, _ in regressions]
                  + [a["userId"] for uid, _, _, a in regressions if a and uid in ("G1a", "G1c", "G4", "G6a", "G10a")]
                  + [x["userId"] for uid, a, b in thresholds for x in (a, b)
                     if uid in ("v3-reserve-3m", "installment-36pct", "v3-netdebt-5y", "v3-netdebt-15y",
                                "savings-0pct", "expense-80pct", "v3-expense-floor", "v3-interest-floor",
                                "v3-runway-25y")])
    gold = golden([everything[u] for u in golden_ids],
                  (lambda uid: scores["v2"][uid]["score"]) if live_v2 else (lambda uid: frozen_gold.get(uid)))

    all_ids = list(everything)
    results = {
        "parameters": {"n": args.n, "stress": args.stress, "seed": args.seed,
                       "scorer": DLL.relative_to(ROOT).as_posix(), "scorerVersion": scorer_version,
                       "profilesScored": len(allp),
                       "v3Variants": {k: v.maxima for k, v in v3.VARIANTS.items()}},
        "calibration": cal,
        "segments": segments(core, scores),
        "v3Diagnostics": diagnostics(core),
        "fragilityTargets": {"lastsOver2Months (Findex 2025)": 0.223,
                             "cannotCoverUnexpected (Eurostat 2025)": 0.251},
        "rankCorrelation": rank_correlations(core, scores),
        "jumpAndMonotonicity": jump_and_monotonicity(bases, scores, perts),
        "gaming": gaming(core, scores),
        "warnings": warning_consistency(all_ids, scores),
        "appliedRules": rules_by_stratum(core + stress + demos, scores),
        "demos": side_by_side([d["userId"] for d in demos], scores),
        "regressionProbes": pair_table(regressions, scores),
        "thresholdProbes": threshold_table(thresholds, scores),
    }
    if not live_v2:
        results["csharpPortCheck"] = port_check(scores)
        merge_frozen_v2(results)
    (OUT / "iq_v3_results.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")
    (OUT / "iq_v3_golden.json").write_text(json.dumps(
        {"description": "Golden table for the C# port of Financial IQ scoring v3 (evaluation/IQ_V3_PROPOSAL.md). "
                        "Produced by evaluation/iq_v3/scoring.py; intermediates rounded to 6 decimals, half-up.",
         "version": v3.VERSION, "profiles": gold}, ensure_ascii=False, indent=1), encoding="utf-8")
    print_calibration(cal)
    print(json.dumps({k: results[k] for k in ("segments", "rankCorrelation", "gaming", "warnings")},
                     ensure_ascii=False, indent=1))
    if "csharpPortCheck" in results:
        print("C# port vs Python:", json.dumps({k: results["csharpPortCheck"][k]
                                                for k in ("variant", "profiles", "mismatches")}))
    for ver in ["v2"] + V3:
        jm = results["jumpAndMonotonicity"][ver]
        print(f"{ver:7} jump max {jm['jump1pct']['max']:>3} p99 {jm['jump1pct']['p99']:>3}  "
              f"monotonicity violations {jm['monotonicity']['violations']:>5} / {jm['monotonicity']['checked']}  "
              f"threshold max {results['thresholdProbes']['maxAbsJump'][ver]}")


if __name__ == "__main__":
    main()
