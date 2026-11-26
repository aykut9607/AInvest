"""Input-output model of the Financial IQ score: how each input reaches the score, what every parameter rests on and
how sensitive the score is. Writes evaluation/iq_model.html (self-contained, Turkish, no network).

    py -3 evaluation/iq_model.py            # v2 (frozen copy in evaluation/out/scorer-v2) vs v3 (this repo's build)
    py -3 evaluation/iq_model.py --scorer v3=<BatchScorer dll or project>   # one scorer only

Every score on the page comes from the production C# rules (FinancialIqCommandManager.CalculateScore) through the
FinancialIQ.BatchScorer tool; nothing here re-implements the scoring. Python builds the input profiles, calls the scorer
(three processes per scorer: a main pass, a pass that locates the cliffs found in the first one, and a last pass that
makes the cheapest +10 changes exact to 1 TL) and summarises the output. The scorer must already be built in Release:
    dotnet build services/financial-iq-service/src/FinancialIQ.BatchScorer -c Release
Each --scorer adds comparison series and columns everywhere; factor-level sections follow each scorer's own factor
keys (v2: 5 step factors and three TL rules; v3: 5 piecewise-linear factors, solvency cap and wealth runway labels).
Standard library only.

What is measured (method notes in evaluation/IQ_MODEL.md):
  - dependency matrix: which factor changes when one input is halved or raised by 50% (rule cases left out)
  - parameter probes: every threshold checked with a pair of profiles 1 TL apart
  - one-at-a-time sweeps around the 8 demo personas (infra/seed/seed_demo_users.py), cliffs refined to a few TL
  - cliff map: largest |score change| for +-1% single-input changes over a sampled population
  - 2-D heatmaps: savings rate x reserve months, income x net worth
  - Sobol indices: Saltelli sampling, Saltelli 2010 first-order and Jansen 1999 total estimators, bootstrap intervals
  - cheapest +10 points per persona
Intermediates go to evaluation/out/iq_model_*.json (git-ignored).
"""

import argparse
import html
import json
import math
import random
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import NamedTuple

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / "out"
PAGE = HERE / "iq_model.html"
REPO_SCORER = (ROOT / "services" / "financial-iq-service" / "src" / "FinancialIQ.BatchScorer" / "bin" / "Release"
               / "net10.0" / "FinancialIQ.BatchScorer.dll")
# default comparison: the v2 rules as frozen before the v3 port, and the repo's current build (v3)
DEFAULT_SCORERS = [("v2", OUT / "scorer-v2" / "FinancialIQ.BatchScorer.dll"), ("v3", REPO_SCORER)]

# key, Turkish name, short name, symbol in the formulas
INPUTS = [
    ("monthlyIncome", "Aylık gelir", "Gelir", "I"),
    ("monthlyExpenses", "Aylık gider", "Gider", "E"),
    ("monthlyDebtPayment", "Aylık taksit", "Taksit", "P"),
    ("totalDebt", "Toplam borç", "Borç", "D"),
    ("cashReserve", "Nakit birikim", "Nakit", "C"),
    ("investmentAmount", "Yatırım", "Yatırım", "V"),
    ("impatienceLevel", "Sabırsızlık (1–5)", "Sabırsızlık", "S"),
]
KEYS = [k for k, *_ in INPUTS]
MONEY = KEYS[:6]
INPUT_TR = {k: n for k, n, _, _ in INPUTS}
SHORT_TR = {k: s for k, _, s, _ in INPUTS}
# names of the sampled variables in the Sobol tables (the installment follows from the debt and a repayment term)
SOBOL_TR = {**INPUT_TR, "monthlyDebtPayment": "Vade (taksiti belirler)", "totalDebt": "Borç (taksiti de büyütür)",
            "monthlyIncome": "Gelir düzeyi"}
SOBOL_SHORT = {**SHORT_TR, "monthlyDebtPayment": "Vade", "totalDebt": "Borç", "monthlyIncome": "Gelir düzeyi"}

FACTOR_TR = {"CashReserveMonths": "Acil durum fonu", "DebtToIncomeRatio": "Borç yükü", "SavingsRate": "Tasarruf",
             "ExpenseRatio": "Gider oranı", "Impatience": "Sabırsızlık", "InstallmentToIncome": "Taksit oranı",
             "NetDebtToIncome": "Net borç"}
RULE_TR = {"VERY_HIGH_INCOME": "Çok yüksek gelir → 100", "VERY_HIGH_WEALTH": "Çok yüksek servet → 100",
           "EXTREME_DEBT": "Aşırı borç → 0", "SOLVENCY_CAP": "Ödeme gücü tavanı", "WEALTH_RUNWAY": "Servet pisti"}
# rules that set or scale every factor at once (v2's three TL rules, v3's solvency cap); the dependency matrix leaves
# these cases out. v3's WEALTH_RUNWAY only lifts two factors and is part of the factor mechanics, so it stays in.
OVERRIDE_RULES = {"VERY_HIGH_INCOME", "VERY_HIGH_WEALTH", "EXTREME_DEBT", "SOLVENCY_CAP"}
V2_KEYS = ["CashReserveMonths", "DebtToIncomeRatio", "SavingsRate", "ExpenseRatio", "Impatience"]
V3_KEYS = ["CashReserveMonths", "InstallmentToIncome", "NetDebtToIncome", "SavingsRate", "Impatience"]
# v2 step labels for the cliff causes: (factor, higher points, lower points) -> threshold
V2_STEPS = {
    ("CashReserveMonths", 25, 15): "rezerv 6 ay", ("CashReserveMonths", 15, 8): "rezerv 3 ay",
    ("CashReserveMonths", 8, 0): "rezerv 1 ay",
    ("DebtToIncomeRatio", 25, 15): "taksit %10 / net borç 0,5 yıl", ("DebtToIncomeRatio", 15, 8): "taksit %20 / net borç 1 yıl",
    ("DebtToIncomeRatio", 8, 0): "taksit %36 / net borç 3 yıl",
    ("SavingsRate", 25, 15): "tasarruf %20", ("SavingsRate", 15, 8): "tasarruf %10", ("SavingsRate", 8, 0): "tasarruf 0",
    ("ExpenseRatio", 15, 9): "gider %40", ("ExpenseRatio", 9, 5): "gider %60", ("ExpenseRatio", 5, 0): "gider %80",
}


def prof(income, expenses, payment=0, debt=0, cash=0, investments=0, impatience=3) -> dict:
    return {"monthlyIncome": income, "monthlyExpenses": expenses, "monthlyDebtPayment": payment, "totalDebt": debt,
            "cashReserve": cash, "investmentAmount": investments, "impatienceLevel": impatience}


# the demo accounts of infra/seed/seed_demo_users.py (same numbers as evaluation/playground.py's presets);
# the trend account is shown with its last (4th) profile
PERSONAS = [
    ("low", "Zayıf (LOW)", "Düşük rezerv, aylık açık, aşırı harcama, sabırsız", prof(30000, 25000, 7000, 90000, 3000, 10000, 5)),
    ("medium", "Orta (MEDIUM)", "2 aylık rezerv, %16 taksit, %24 tasarruf", prof(50000, 30000, 8000, 0, 60000, 0, 3)),
    ("high", "Güçlü (HIGH)", "Sağlıklı oranlar, kural yok", prof(20000, 8000, 2000, 0, 30000, 0, 2)),
    ("highdebt", "Gizli borç", "Taksit küçük ama net borç 4 yıllık gelir", prof(40000, 16000, 2000, 2000000, 50000, 0, 2)),
    ("richincome", "Kural: çok yüksek gelir", "Ayda 1.000.000 gelir, nakit yok", prof(1000000, 900000, 0, 0, 0, 0, 5)),
    ("richwealth", "Kural: çok yüksek servet", "Küçük maaş, 10.000.000 net servet", prof(30000, 29000, 0, 1000000, 2000000, 9000000, 5)),
    ("extremedebt", "Kural: aşırı borç", "Net borç 100.000.000'un üstünde", prof(40000, 16000, 4000, 120000000, 96000, 10000000, 1)),
    ("trend", "Gelişim (son profil)", "demo.trend hesabının 4. hesaplaması", prof(30000, 15000, 3000, 30000, 90000, 20000, 2)),
]

FAVOURABLE = {"monthlyIncome": 1, "monthlyExpenses": -1, "monthlyDebtPayment": -1, "totalDebt": -1,
              "cashReserve": 1, "investmentAmount": 1}


# --- formatting -------------------------------------------------------------------------------------------------------
def esc(value) -> str:
    return html.escape(str(value), quote=True)


def num(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def pct(rate: float | None, decimals: int = 1) -> str:
    if rate is None:
        return "–"
    if 0 < abs(rate) < 0.5 * 10 ** (-decimals - 2):  # would print as 0
        return "<%" + num(10 ** -decimals, decimals)
    text = num(abs(rate) * 100, decimals)
    if decimals and text.endswith("," + "0" * decimals):
        text = text[: -(decimals + 1)]
    return ("−" if rate < 0 else "") + "%" + text


def tl(value: float) -> str:
    return num(value, 0 if abs(value - round(value)) < 0.005 else 2) + " TL"


def signed(value: float) -> str:
    return ("+" if value > 0 else "−" if value < 0 else "±") + num(abs(value))


def idx(value: float) -> str:
    """A Sobol index: two decimals, three when it would otherwise print as 0,00."""
    return num(value, 3 if 0 < abs(value) < 0.005 else 2)


def money_short(value: float) -> str:
    a, sign = abs(value), "−" if value < 0 else ""
    if a >= 1e6:
        return sign + num(a / 1e6, 0 if a >= 1e7 or a % 1e6 == 0 else 1) + " Mn"
    if a >= 1e3:
        return sign + num(a / 1e3, 0 if a >= 1e4 or a % 1e3 == 0 else 1) + " bin"
    return sign + num(a)


# --- the scorer -------------------------------------------------------------------------------------------------------
class Res(NamedTuple):
    score: int
    segment: str
    factors: dict
    rule: str | None
    warnings: tuple
    version: str
    maxima: dict | None  # factorMaximums (v3 breakdowns carry it; v2 does not)


def resolve_dll(path: Path) -> Path:
    if path.suffix.lower() == ".dll":
        dll = path
    else:
        project = path.parent if path.suffix.lower() == ".csproj" else path
        if (project / "FinancialIQ.BatchScorer").is_dir():  # the src folder was given
            project = project / "FinancialIQ.BatchScorer"
        dll = project / "bin" / "Release" / "net10.0" / "FinancialIQ.BatchScorer.dll"
    if not dll.exists():
        hint = "Build it first: dotnet build <FinancialIQ.BatchScorer project> -c Release"
        if "scorer-v2" in dll.as_posix():  # the frozen v2 copy is git-ignored; rebuild it from the last v2 commit
            hint = ("The frozen v2 scorer is not in this checkout (evaluation/out is git-ignored). Rebuild it:\n"
                    "  git worktree add ../AInvest-v2 a03d197\n"
                    "  dotnet build ../AInvest-v2/services/financial-iq-service/src/FinancialIQ.BatchScorer -c Release\n"
                    "then pass --scorer v2=../AInvest-v2/services/financial-iq-service/src/FinancialIQ.BatchScorer "
                    "(or copy its bin/Release/net10.0 into evaluation/out/scorer-v2/)")
        sys.exit(f"BatchScorer not found: {dll}\n{hint}")
    return dll


def shown_path(path: Path) -> str:
    """Repo-relative when inside the repo, so no personal directory ends up on the page."""
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return "external: " + path.name


class Scorer:
    def __init__(self, label: str, path: Path):
        self.label, self.dll = label, resolve_dll(path)
        self.processes, self.scored, self.version = 0, 0, "?"

    def score(self, profiles: list[dict], tag: str) -> list[Res | None]:
        src, dst = OUT / f"iq_model_{self.label}_{tag}.in.json", OUT / f"iq_model_{self.label}_{tag}.out.json"
        items = [{"userId": str(i), **p} for i, p in enumerate(profiles)]
        src.write_text(json.dumps(items, separators=(",", ":")), encoding="utf-8")
        run = subprocess.run(["dotnet", str(self.dll), str(src), str(dst)], capture_output=True, text=True)
        if run.returncode != 0:
            sys.exit(f"BatchScorer ({self.label}) failed: {run.stderr.strip()[:500]}")
        self.processes += 1
        out: list[Res | None] = [None] * len(profiles)
        for r in json.loads(dst.read_text(encoding="utf-8")):
            fb = r["factorBreakdown"]
            out[int(r["userId"])] = Res(r["score"], r["segment"], fb.get("factors", {}), fb.get("appliedRule"),
                                        tuple(fb.get("warnings", [])), fb.get("version", "v1"), fb.get("factorMaximums"))
        self.scored += sum(r is not None for r in out)
        return out


class Batch:
    """Profiles of all sections in one list, so one scorer process scores them all."""

    def __init__(self):
        self.items: list[dict] = []

    def add(self, profiles: list[dict]) -> range:
        start = len(self.items)
        self.items.extend(profiles)
        return range(start, len(self.items))


def changed(p: dict, **values) -> dict:
    q = dict(p)
    q.update(values)
    return q


# --- section: sweeps (one input at a time) ----------------------------------------------------------------------------
def sweep_values(p: dict, key: str, n: int = 400) -> list[float]:
    if key == "impatienceLevel":
        return [1, 2, 3, 4, 5]
    b, inc = p[key], p["monthlyIncome"]
    spend = max(p["monthlyExpenses"], 0.3 * inc)
    lo, hi = {
        "monthlyIncome": (max(1000.0, 0.25 * b), 3.0 * b),
        "monthlyExpenses": (0.0, max(2.0 * b, 1.2 * inc)),
        "monthlyDebtPayment": (0.0, max(2.0 * b, 0.6 * inc)),
        "totalDebt": (0.0, max(2.0 * b, 48.0 * inc)),
        "cashReserve": (0.0, max(2.0 * b, 9.0 * spend)),
        "investmentAmount": (0.0, max(2.0 * b, 18.0 * spend)),
    }[key]
    return sorted({round(lo + (hi - lo) * k / n) for k in range(n + 1)} | {b})


def signature(r: Res, factor_keys: list[str]) -> tuple:
    return r.score, r.rule, tuple(r.factors.get(k) for k in factor_keys)


def runs_of(points: list[tuple[float, Res]], factor_keys: list[str], rules: list[str]) -> list[list]:
    """Consecutive points with the same score, rule and factor points -> [first x, last x, score, rule, factors]."""
    out, last = [], None
    for x, r in points:
        sig = signature(r, factor_keys)
        if out and sig == last:
            out[-1][1] = x
        else:
            out.append([x, x, r.score, rules.index(r.rule) if r.rule else -1, list(sig[2])])
            last = sig
    return out


def gap_values(a: float, b: float, n: int = 120) -> list[float]:
    """Integer points strictly between a and b (all of them when the gap is small)."""
    lo, hi = math.floor(a) + 1, math.ceil(b) - 1
    if hi < lo:
        return []
    if hi - lo + 1 <= n:
        return list(range(lo, hi + 1))
    return sorted({round(lo + (hi - lo) * k / (n - 1)) for k in range(n)})


# --- section: cheapest +10 points -------------------------------------------------------------------------------------
def cheapest_values(p: dict, key: str) -> list[float]:
    """Candidate values in the favourable direction, ordered from the smallest change to the largest."""
    b, inc = p[key], p["monthlyIncome"]
    if FAVOURABLE[key] < 0:
        if b <= 0:
            return []
        shares = [0.0005 * (2000 ** (k / 300)) for k in range(301)]  # 0.05% .. 100% less
        values = [round(b * (1 - min(s, 1.0)), 2) for s in shares]
    else:
        top = 20.0 if key == "monthlyIncome" else 600.0  # at most 20x the income / 50 years of income added
        values = [round(b + inc * 0.0005 * ((top / 0.0005) ** (k / 400)), 2) for k in range(401)]
    seen, ordered = set(), []
    for v in values:
        if v not in seen and v != b:
            seen.add(v)
            ordered.append(v)
    return ordered


# --- section: population (Sobol, cliffs, dependency probes) -----------------------------------------------------------
def loguni(t: float, a: float, b: float) -> float:
    return a * (b / a) ** t


def mixture(u: float, parts: list) -> float:
    acc = 0.0
    for i, (weight, fn) in enumerate(parts):
        if u < acc + weight or i == len(parts) - 1:
            return fn(min(max((u - acc) / weight, 0.0), 1.0))
        acc += weight
    raise AssertionError


def _zero(_t: float) -> float:
    return 0.0


# variable shown, distribution (Turkish), inverse CDF of u in [0, 1); one per input in KEYS order.
# Scale-free on purpose: every amount is drawn relative to the income, so the variables are independent and the
# combinations stay plausible; the tails make the rules reachable. The installment is not drawn on its own: it follows
# from the debt and a drawn repayment term (see population_profile), so debt and installment stay consistent and
# v3's 3.5% interest floor binds only where the term (or a debt too big to service) makes it bind.
DEBTOR_SHARE = 0.56  # TBB Risk Merkezi: about 56% of adults have a loan (the team's realism check)
STRAY_INSTALLMENT_SHARE = 0.10  # of the people without debt: an installment with no debt reported (data error), 4.4%
MAX_INSTALLMENT_SHARE = 0.6  # nobody services more than 60% of the income; a bigger annuity means a longer real term
DISTRIBUTIONS = [
    ("Gelir düzeyi (TL/ay)", "%90 log-tekdüze 15.000–150.000; %10 log-tekdüze 150.000–2.500.000 (zengin kuyruk)",
     lambda u: mixture(u, [(0.9, lambda t: loguni(t, 15_000, 150_000)), (0.1, lambda t: loguni(t, 150_000, 2_500_000))])),
    ("Gider / gelir", "tekdüze 0,20–1,10", lambda u: 0.2 + 0.9 * u),
    ("Geri ödeme vadesi → taksit",
     "borçluda vade log-tekdüze 6–240 ay; aylık faiz vadeyle %4'ten %1,5'e iner (kısa tüketici kredisi → uzun konut "
     "kredisi); taksit = annüite, en fazla gelirin %60'ı. Borçsuzların %10'unda borçsuz taksit (gelirin %2–12'si)",
     lambda u: u),
    ("Toplam borç / yıllık gelir",
     f"%{round((1 - DEBTOR_SHARE) * 100)} borçsuz; %52 log-tekdüze 0,05–2,5; %4 log-tekdüze 2,5–40",
     lambda u: mixture(u, [(1 - DEBTOR_SHARE, _zero), (0.52, lambda t: loguni(t, 0.05, 2.5)),
                           (DEBTOR_SHARE - 0.52, lambda t: loguni(t, 2.5, 40))])),
    ("Nakit / aylık gelir", "%15 sıfır; %82 log-tekdüze 0,1–24; %3 log-tekdüze 24–240",
     lambda u: mixture(u, [(0.15, _zero), (0.82, lambda t: loguni(t, 0.1, 24)), (0.03, lambda t: loguni(t, 24, 240))])),
    ("Yatırım / aylık gelir", "%40 sıfır; %57 log-tekdüze 0,5–48; %3 log-tekdüze 48–600",
     lambda u: mixture(u, [(0.4, _zero), (0.57, lambda t: loguni(t, 0.5, 48)), (0.03, lambda t: loguni(t, 48, 600))])),
    ("Sabırsızlık", "1–5 eşit olasılıklı", lambda u: min(5, int(u * 5) + 1)),
]


def repayment(debt: float, income: float, u: float) -> float:
    """Monthly installment of a loan from the drawn term: an annuity at a rate that falls with the term."""
    if debt <= 0:  # a few people report an installment without any debt (the data error v3 warns about)
        if u < STRAY_INSTALLMENT_SHARE:
            return income * (0.02 + 0.10 * u / STRAY_INSTALLMENT_SHARE)
        return 0.0
    term = loguni(u, 6, 240)  # months
    rate = min(0.04, max(0.015, 0.04 - 0.025 * (term - 36) / (240 - 36)))  # monthly
    annuity = rate / (1 - (1 + rate) ** -term)
    return min(debt * annuity, MAX_INSTALLMENT_SHARE * income)


def population_profile(u: list[float]) -> dict:
    z = [fn(x) for (_, _, fn), x in zip(DISTRIBUTIONS, u)]
    income = round(z[0], 2)
    debt = round(12 * income * z[3], 2)
    return prof(income, round(income * z[1], 2), round(repayment(debt, income, z[2]), 2), debt,
                round(income * z[4], 2), round(income * z[5], 2), int(z[6]))


def wide_profile(u: list[float]) -> dict:
    """Dependency-matrix sample: like the population, but the installment is drawn on its own (25% none, else up to
    60% of the income) and independently of the debt, so every structural input-factor link gets exercised."""
    z = [fn(x) for (_, _, fn), x in zip(DISTRIBUTIONS, u)]
    income = round(z[0], 2)
    payment = 0.0 if u[2] < 0.25 else 0.6 * (u[2] - 0.25) / 0.75
    return prof(income, round(income * z[1], 2), round(income * payment, 2), round(12 * income * z[3], 2),
                round(income * z[4], 2), round(income * z[5], 2), int(z[6]))


def sobol_indices(ya: list[float], yb: list[float], yab: list[list[float]], idx: list[int]) -> tuple[list, list, float]:
    """Saltelli 2010 first-order and Jansen 1999 total-effect estimators over the rows idx."""
    a = [ya[j] for j in idx]
    b = [yb[j] for j in idx]
    both = a + b
    mean = sum(both) / len(both)
    var = sum((v - mean) ** 2 for v in both) / len(both)
    a = [v - mean for v in a]
    b = [v - mean for v in b]
    n = len(idx)
    first, total = [], []
    for col in yab:
        ab = [col[j] - mean for j in idx]
        first.append(sum(bb * (x - aa) for bb, x, aa in zip(b, ab, a)) / n / var if var else 0.0)
        total.append(sum((aa - x) ** 2 for aa, x in zip(a, ab)) / (2 * n) / var if var else 0.0)
    return first, total, var


# --- section: fixed probes (parameter table) and 1 TL witnesses -------------------------------------------------------
PROBE_BASE = prof(100_000, 30_000, 5_000, 0, 300_000, 0, 1)  # every factor at its maximum, far from all thresholds

# group, parameter, value, meaning, evidence level, source, factor, probe pair (at the threshold, 1 TL past it)
PARAMS = [
    ("Ara değişken", "Yatırımın rezerve sayılan payı", "0,5", "rezerv = nakit + 0,5 × yatırım; net borçta yatırımın tamamı sayılır",
     "kısmi", "Basel III LCR likidite iskontosu benzetmesi", "CashReserveMonths",
     (changed(PROBE_BASE, cashReserve=0, investmentAmount=180_000), changed(PROBE_BASE, cashReserve=0, investmentAmount=179_998))),
    ("Acil durum fonu (25)", "Rezerv ≥ 6 ay", "25 puan", "rezervin aylık gidere oranı", "kısmi",
     "6 aylık fon önerisi (kısmi dayanak)", "CashReserveMonths",
     (changed(PROBE_BASE, cashReserve=180_000), changed(PROBE_BASE, cashReserve=179_999))),
    ("Acil durum fonu (25)", "Rezerv ≥ 3 ay", "15 puan", "", "güçlü", "Greninger ve ark. 1996 (156 uzmanlı Delphi): 3 aylık fon",
     "CashReserveMonths", (changed(PROBE_BASE, cashReserve=90_000), changed(PROBE_BASE, cashReserve=89_999))),
    ("Acil durum fonu (25)", "Rezerv ≥ 1 ay", "8 puan", "altı 0 puan", "dayanaksız", "dayanak bulunamadı",
     "CashReserveMonths", (changed(PROBE_BASE, cashReserve=30_000), changed(PROBE_BASE, cashReserve=29_999))),
    ("Borç yükü (25)", "Taksit / gelir ≤ %10", "25 puan", "faktör = iki ölçünün kötüsü (taksit ve net borç)", "güçlü",
     "Greninger ve ark. 1996", "DebtToIncomeRatio",
     (changed(PROBE_BASE, monthlyDebtPayment=10_000), changed(PROBE_BASE, monthlyDebtPayment=10_001))),
    ("Borç yükü (25)", "Taksit / gelir ≤ %20", "15 puan", "", "güçlü", "Greninger ve ark. 1996", "DebtToIncomeRatio",
     (changed(PROBE_BASE, monthlyDebtPayment=20_000), changed(PROBE_BASE, monthlyDebtPayment=20_001))),
    ("Borç yükü (25)", "Taksit / gelir ≤ %36", "8 puan", "eşik değeri", "kısmi", "28/36 kuralı (Fannie Mae)",
     "DebtToIncomeRatio", (changed(PROBE_BASE, monthlyDebtPayment=36_000), changed(PROBE_BASE, monthlyDebtPayment=36_001))),
    ("Borç yükü (25)", "Taksit / gelir > %36", "0 puan + uyarı", "“High debt burden”: kırılgan bant", "güçlü",
     "Greninger ve ark. 1996: %36 üstü kırılgan", "DebtToIncomeRatio",
     (changed(PROBE_BASE, monthlyDebtPayment=36_000), changed(PROBE_BASE, monthlyDebtPayment=36_001))),
    ("Borç yükü (25)", "Net borç ≤ 0,5 yıllık gelir", "25 puan", "net borç = borç − nakit − yatırım", "dayanaksız",
     "dayanak bulunamadı", "DebtToIncomeRatio",
     (changed(PROBE_BASE, totalDebt=900_000), changed(PROBE_BASE, totalDebt=900_001))),
    ("Borç yükü (25)", "Net borç ≤ 1 yıllık gelir", "15 puan", "", "dayanaksız", "dayanak bulunamadı", "DebtToIncomeRatio",
     (changed(PROBE_BASE, totalDebt=1_500_000), changed(PROBE_BASE, totalDebt=1_500_001))),
    ("Borç yükü (25)", "Net borç ≤ 3 yıllık gelir", "8 puan", "üstü 0 + “High total debt”", "dayanaksız",
     "dayanak bulunamadı", "DebtToIncomeRatio",
     (changed(PROBE_BASE, totalDebt=3_900_000), changed(PROBE_BASE, totalDebt=3_900_001))),
    ("Tasarruf (25)", "Tasarruf oranı ≥ %20", "25 puan", "(gelir − gider − taksit) / gelir", "kısmi", "50/30/20 kuralı",
     "SavingsRate", (changed(PROBE_BASE, monthlyDebtPayment=50_000), changed(PROBE_BASE, monthlyDebtPayment=50_001))),
    ("Tasarruf (25)", "Tasarruf oranı ≥ %10", "15 puan", "", "güçlü", "Greninger ve ark. 1996", "SavingsRate",
     (changed(PROBE_BASE, monthlyDebtPayment=60_000), changed(PROBE_BASE, monthlyDebtPayment=60_001))),
    ("Tasarruf (25)", "Tasarruf oranı ≥ 0", "8 puan", "altı 0 + “Negative savings rate”", "dayanaksız", "dayanak bulunamadı",
     "SavingsRate", (changed(PROBE_BASE, monthlyDebtPayment=70_000), changed(PROBE_BASE, monthlyDebtPayment=70_001))),
    ("Gider oranı (15)", "Gider / gelir ≤ %40", "15 puan", "", "dayanaksız", "dayanak bulunamadı", "ExpenseRatio",
     (changed(PROBE_BASE, monthlyExpenses=40_000), changed(PROBE_BASE, monthlyExpenses=40_001))),
    ("Gider oranı (15)", "Gider / gelir ≤ %60", "9 puan", "", "dayanaksız", "dayanak bulunamadı", "ExpenseRatio",
     (changed(PROBE_BASE, monthlyExpenses=60_000), changed(PROBE_BASE, monthlyExpenses=60_001))),
    ("Gider oranı (15)", "Gider / gelir ≤ %80", "5 puan", "üstü 0 + “Overspending…”", "kısmi", "kısmi dayanak",
     "ExpenseRatio", (changed(PROBE_BASE, monthlyExpenses=80_000), changed(PROBE_BASE, monthlyExpenses=80_001))),
    ("Kural", "VERY_HIGH_INCOME", "gelir ≥ 1.000.000 ve net borç ≤ 1 yıllık gelir → 100", "1. öncelik", "dayanaksız",
     "incelenen literatürde emsali yok", None,
     (prof(1_000_000, 900_000, 0, 0, 0, 0, 5), prof(999_999, 900_000, 0, 0, 0, 0, 5))),
    ("Kural", "VERY_HIGH_INCOME borç sınırı", "net borç ≤ 12 × aylık gelir", "", "dayanaksız",
     "incelenen literatürde emsali yok", None,
     (prof(1_000_000, 900_000, 0, 12_000_000, 0, 0, 5), prof(1_000_000, 900_000, 0, 12_000_001, 0, 0, 5))),
    ("Kural", "VERY_HIGH_WEALTH", "net servet ≥ 10.000.000 → 100", "2. öncelik", "dayanaksız",
     "incelenen literatürde emsali yok", None,
     (prof(30_000, 29_000, 0, 1_000_000, 2_000_000, 9_000_000, 5), prof(30_000, 29_000, 0, 1_000_001, 2_000_000, 9_000_000, 5))),
    ("Kural", "EXTREME_DEBT", "net borç ≥ 100.000.000 (gelir < 1.000.000) → 0", "3. öncelik", "dayanaksız",
     "incelenen literatürde emsali yok", None,
     (prof(40_000, 16_000, 4_000, 110_096_000, 96_000, 10_000_000, 1), prof(40_000, 16_000, 4_000, 110_095_999, 96_000, 10_000_000, 1))),
]
IMPATIENCE_PROBES = [changed(PROBE_BASE, impatienceLevel=s) for s in range(1, 6)]

# v3 anchors (evaluation/IQ_V3_PROPOSAL.md 8.3), read back from the scorer at profiles that sit exactly on each anchor.
# Base: income 100.000, expenses 30.000, installment 5.000 -> monthly outflow O = 35.000; cash 210.000 = 6 x O, so the
# liquid assets exactly fill the emergency target and nothing offsets the debt (X = 0).
# group, anchor, share, evidence, source, factor (None = total score), probe profiles (several -> values joined by " / ")
V3_BASE = prof(100_000, 30_000, 5_000, 0, 210_000, 0, 1)
PARAMS_V3 = [
    ("Acil durum fonu (30)", "Rezerv 0 ay", "pay 0", "yargı", "alt uç", "CashReserveMonths",
     [changed(V3_BASE, cashReserve=0)]),
    ("Acil durum fonu (30)", "Rezerv 3 ay (uyarı çizgisi)", "pay 0,6", "güçlü", "Greninger ve ark. 1996",
     "CashReserveMonths", [changed(V3_BASE, cashReserve=105_000)]),
    ("Acil durum fonu (30)", "Rezerv 6 ay", "pay 1", "kısmi", "6 aylık fon önerisi", "CashReserveMonths",
     [changed(V3_BASE, cashReserve=210_000)]),
    ("Taksit oranı (25)", "Taksit / gelir %10", "pay 1", "güçlü", "Greninger ve ark. 1996", "InstallmentToIncome",
     [changed(V3_BASE, monthlyDebtPayment=10_000, cashReserve=0)]),
    ("Taksit oranı (25)", "Taksit / gelir %20", "pay 0,6", "güçlü", "Greninger ve ark. 1996", "InstallmentToIncome",
     [changed(V3_BASE, monthlyDebtPayment=20_000, cashReserve=0)]),
    ("Taksit oranı (25)", "Taksit / gelir %36", "pay 0,2", "güçlü", "Greninger: %36 üstü kırılgan; 28/36 kuralı (kısmi)",
     "InstallmentToIncome", [changed(V3_BASE, monthlyDebtPayment=36_000, cashReserve=0)]),
    ("Taksit oranı (25)", "Taksit / gelir %50", "pay 0", "yargı", "alt uç", "InstallmentToIncome",
     [changed(V3_BASE, monthlyDebtPayment=50_000, cashReserve=0)]),
    ("Net borç (10)", "Net borç 0,5 / 1 / 3 yıllık gelir", "pay 1 / 0,6 / 0,2", "dayanaksız", "v2'nin eşikleri",
     "NetDebtToIncome", [changed(V3_BASE, totalDebt=d) for d in (600_000, 1_200_000, 3_600_000)]),
    ("Net borç (10)", "Net borç 5 yıllık gelir", "pay 0", "yargı", "alt uç", "NetDebtToIncome",
     [changed(V3_BASE, totalDebt=6_000_000)]),
    ("Tasarruf (30)", "Tasarruf %20", "pay 1", "kısmi", "50/30/20 kuralı", "SavingsRate",
     [changed(V3_BASE, monthlyDebtPayment=50_000, cashReserve=0)]),
    ("Tasarruf (30)", "Tasarruf %10 (uyarı çizgisi)", "pay 0,6", "güçlü", "Greninger ve ark. 1996", "SavingsRate",
     [changed(V3_BASE, monthlyDebtPayment=60_000, cashReserve=0)]),
    ("Tasarruf (30)", "Tasarruf 0 / −%10", "pay 0,2 / 0", "yargı", "alt uç", "SavingsRate",
     [changed(V3_BASE, monthlyDebtPayment=p, cashReserve=0) for p in (70_000, 80_000)]),
    ("Sabırsızlık (5)", "Sabırsızlık 1 … 5", "pay 1 / 0,8 / 0,6 / 0,2 / 0", "dayanaksız",
     "tek maddelik öz-beyan; öz-algı göstergesi", "Impatience", [changed(V3_BASE, impatienceLevel=k) for k in range(1, 6)]),
    ("Ara değişken", "Likit pay: yatırımın yarısı", "0,5", "kısmi", "Basel III LCR 2B kesintisi", "CashReserveMonths",
     [changed(V3_BASE, cashReserve=105_000), changed(V3_BASE, cashReserve=0, investmentAmount=210_000)]),
    ("Ara değişken", "Yalnız fon hedefinin (6 ay) üstü borçtan düşer: borç 1,8 Mn, hedef üstü likit 0 / 0,6 / 1,2 Mn", "6 ay", "kısmi", "6 aylık fon önerisi",
     "NetDebtToIncome", [changed(V3_BASE, totalDebt=1_800_000, cashReserve=c) for c in (210_000, 810_000, 1_410_000)]),
    ("Ara değişken", "Faiz tabanı: taksit en az net borcun %3,5'i", "%3,5 / ay", "yargı",
     "IQ servisindeki DebtPayoffRules varsayımı", "InstallmentToIncome",
     [changed(V3_BASE, totalDebt=1_200_000), changed(V3_BASE, totalDebt=1_200_000, monthlyDebtPayment=42_000, cashReserve=432_000)]),
    ("Ara değişken", "Gider tabanı: gelirin %10'u", "%10", "yargı", "gider 0 oyununu kapatır", None,
     [changed(V3_BASE, monthlyExpenses=0), changed(V3_BASE, monthlyExpenses=10_000)]),
    ("Tavan ve pist", "Ödeme gücü tavanı κ: net borç 5 / 10 / 15 yıllık gelir", "κ 1 / 0,5 / 0", "yargı",
     "%36 ile faizsiz geri ödeme 14 / 42 yıl", None,
     [changed(V3_BASE, totalDebt=d) for d in (6_000_000, 12_000_000, 18_000_000)]),
    ("Tavan ve pist", "Servet pisti λ: likit net servet 0,5 / 12,5 / 25 yıllık gider", "λ 0,02 / 0,5 / 1", "kısmi",
     "%4 kuralı (Bengen 1994, ABD verisi)", "SavingsRate",
     [prof(100_000, 95_000, 0, 0, c, 0, 1) for c in (570_000, 14_250_000, 28_500_000)]),
]

# title, which input moved by 1 TL, before, after, rule-driven?
WITNESSES = [
    ("Gider 1 TL artınca üç eşik birden geçiliyor (rezerv 6 ay, tasarruf %20, gider %40)", "monthlyExpenses",
     prof(100_000, 40_000, 40_000, 0, 240_000, 0, 1), prof(100_000, 40_001, 40_000, 0, 240_000, 0, 1), False),
    ("Gelir 1 TL düşünce üç eşik birden (tasarruf %20, net borç 0,5 yıl, gider %80)", "monthlyIncome",
     prof(100_000, 80_000, 0, 1_400_000, 800_000, 0, 1), prof(99_999, 80_000, 0, 1_400_000, 800_000, 0, 1), False),
    ("Nakit 1 TL azalınca iki faktör birden (rezerv 6 ay, net borç 0,5 yıl)", "cashReserve",
     prof(100_000, 50_000, 5_000, 900_000, 300_000, 0, 1), prof(100_000, 50_000, 5_000, 900_000, 299_999, 0, 1), False),
    ("“Çok yüksek gelir” kişisi, gelir 1 TL düşük", "monthlyIncome",
     prof(1_000_000, 900_000, 0, 0, 0, 0, 5), prof(999_999, 900_000, 0, 0, 0, 0, 5), True),
    ("“Çok yüksek servet” kişisi, yatırım 1 TL düşük", "investmentAmount",
     prof(30_000, 29_000, 0, 1_000_000, 2_000_000, 9_000_000, 5), prof(30_000, 29_000, 0, 1_000_000, 2_000_000, 8_999_999, 5), True),
    ("Güçlü oranlar, net borç tam 100.000.000 (borç 1 TL fazla)", "totalDebt",
     prof(40_000, 16_000, 4_000, 110_095_999, 96_000, 10_000_000, 1), prof(40_000, 16_000, 4_000, 110_096_000, 96_000, 10_000_000, 1), True),
    ("Kuramsal üst sınır: skoru 0 olan profil, gelir 1 TL artınca 100", "monthlyIncome",
     prof(999_999, 2_000_000, 400_000, 0, 0, 0, 5), prof(1_000_000, 2_000_000, 400_000, 0, 0, 0, 5), True),
]


# --- section: heatmaps ------------------------------------------------------------------------------------------------
def heat_savings_reserve() -> dict:
    income, installment = 50_000, 4_000  # installment 8% of income: debt factor 25 everywhere, no net debt
    xs = [k / 100 for k in range(-30, 61)]  # savings rate
    ys = [k / 4 for k in range(0, 49)]  # reserve months
    grid = []
    for m in ys:
        for s in xs:
            expenses = round(income * (1 - installment / income - s))
            grid.append(prof(income, expenses, installment, 0, round(m * expenses), 0, 3))
    return {"id": "heat-sr", "xs": xs, "ys": ys, "grid": grid,
            "xLabel": "Tasarruf oranı", "yLabel": "Rezerv (ay)", "xFmt": "pct", "yFmt": "months",
            "xTicks": [[xs.index(v / 100), pct(v / 100, 0)] for v in (-30, -20, -10, 0, 10, 20, 30, 40, 50, 60)],
            "yTicks": [[ys.index(v), num(v)] for v in (0, 1, 3, 6, 9, 12)],
            "fixed": "Gelir 50.000 TL, taksit 4.000 TL (%8), borç ve yatırım yok, sabırsızlık 3. Gider tasarruf oranından "
                     "türetiliyor: gider = gelir − taksit − tasarruf, yani gider oranı da yatay eksende değişiyor "
                     "(tasarruf %20 ⇔ gider %72). Nakit = rezerv ayı × gider."}


def signed_log_values() -> list[float]:
    neg = [-round(10 ** (8.5 - 0.1 * k)) for k in range(46)]  # -316 Mn .. -10 bin
    pos = [round(10 ** (4 + 0.1 * k)) for k in range(38)]  # 10 bin .. 50 Mn
    return neg + [0] + pos


def heat_income_networth() -> dict:
    xs = [round(10 ** (4 + 0.05 * k)) for k in range(51)]  # income 10 bin .. 3,16 Mn, 1 Mn exactly at k = 40
    ys = signed_log_values()
    grid = []
    for nw in ys:
        for income in xs:
            expenses = round(0.5 * income)
            cash = 3 * expenses
            invest, debt = (nw - cash, 0) if nw >= cash else (0, cash - nw)
            grid.append(prof(income, expenses, round(0.08 * income), debt, cash, invest, 3))

    def nearest(values, v):
        return min(range(len(values)), key=lambda i: abs(values[i] - v))

    return {"id": "heat-in", "xs": xs, "ys": ys, "grid": grid,
            "xLabel": "Aylık gelir (log)", "yLabel": "Net servet (işaretli log)", "xFmt": "tl", "yFmt": "tl",
            "xTicks": [[nearest(xs, v), money_short(v)] for v in (10_000, 100_000, 1_000_000, 3_000_000)],
            "yTicks": [[nearest(ys, v), money_short(v)] for v in (-300_000_000, -100_000_000, -10_000_000, -1_000_000,
                                                                     -100_000, 0, 100_000, 1_000_000, 10_000_000, 50_000_000)],
            "fixed": "Gider gelirin yarısı (%50), taksit %8, nakit 3 aylık gider, sabırsızlık 3. Net servet pozitifse "
                     "fazlası yatırım, negatifse borç olarak yazılıyor. Net servet = nakit + yatırım − borç."}


# --- flow diagrams (hand-drawn per rule set, each checked against its scorer's measured dependency matrix) -----------
# node: id, x, y, width, height, title, lines, kind. edge: (from, to) or (from, to, "cap") for v3's solvency cap, which
# scales every factor; cap edges are drawn but left out of the check (the matrix leaves capped cases out).
FLOW_V2 = {
    "name": "v2", "keys": V2_KEYS, "viewBox": "0 -18 1160 488", "minWidth": 760,
    "columns": [(10, "Girdiler"), (205, "Ara değişkenler"), (600, "Faktörler (basamak fonksiyonları)"),
                (835, "Kurallar (öncelik sırası)")],
    "nodes": [
        ("I", 10, 12, 140, 46, "Aylık gelir I", ["I > 0"], "in"),
        ("E", 10, 76, 140, 46, "Aylık gider E", ["E ≥ 0"], "in"),
        ("P", 10, 140, 140, 46, "Aylık taksit P", ["P ≥ 0"], "in"),
        ("D", 10, 204, 140, 46, "Toplam borç D", ["D ≥ 0"], "in"),
        ("C", 10, 268, 140, 46, "Nakit C", ["C ≥ 0"], "in"),
        ("V", 10, 332, 140, 46, "Yatırım V", ["V ≥ 0"], "in"),
        ("S", 10, 410, 140, 46, "Sabırsızlık S", ["1 … 5 (öz-beyan)"], "in"),
        ("e", 205, 12, 155, 46, "Gider oranı", ["e = E / I"], "mid"),
        ("s", 205, 76, 155, 46, "Tasarruf oranı", ["s = (I − E − P) / I"], "mid"),
        ("p", 205, 140, 155, 46, "Taksit oranı", ["p = P / I"], "mid"),
        ("N", 205, 220, 155, 46, "Net borç", ["N = D − C − V"], "mid"),
        ("R", 205, 300, 155, 46, "Rezerv", ["R = C + 0,5 · V"], "mid"),
        ("Y", 400, 220, 160, 46, "Net borç (yıl)", ["Y = max(N, 0) / 12I"], "mid"),
        ("M", 400, 300, 160, 46, "Rezerv (ay)", ["M = R / E"], "mid"),
        ("F4", 600, 12, 195, 46, "Gider oranı · 15", ["e ≤ %40/60/80 → 15/9/5"], "factor"),
        ("F3", 600, 76, 195, 46, "Tasarruf · 25", ["s ≥ %20/10/0 → 25/15/8"], "factor"),
        ("F2", 600, 150, 195, 62, "Borç yükü · 25", ["min(g(p), h(Y))", "p ≤ %10/20/36 · Y ≤ 0,5/1/3"], "factor"),
        ("F1", 600, 300, 195, 46, "Acil durum fonu · 25", ["M ≥ 6/3/1 ay → 25/15/8"], "factor"),
        ("F5", 600, 410, 195, 46, "Sabırsızlık · 10", ["S = 1…5 → 10/8/5/2/0"], "factor"),
        ("VHI", 835, 12, 170, 46, "1. Çok yüksek gelir", ["I ≥ 1 Mn ve Y ≤ 1 → 100"], "rule"),
        ("VHW", 835, 76, 170, 46, "2. Çok yüksek servet", ["−N ≥ 10 Mn → 100"], "rule"),
        ("ED", 835, 140, 170, 46, "3. Aşırı borç", ["I < 1 Mn, N ≥ 100 Mn → 0"], "rule"),
        ("Q", 1030, 220, 120, 62, "Skor", ["kural varsa kural,", "yoksa F1 + … + F5"], "out"),
        ("SEG", 1030, 320, 120, 78, "Segment", ["0–40 LOW", "41–70 MEDIUM", "71–100 HIGH"], "out"),
    ],
    "edges": [("I", "e"), ("E", "e"), ("I", "s"), ("E", "s"), ("P", "s"), ("P", "p"), ("I", "p"), ("D", "N"),
              ("C", "N"), ("V", "N"), ("C", "R"), ("V", "R"), ("N", "Y"), ("I", "Y"), ("R", "M"), ("E", "M"),
              ("e", "F4"), ("s", "F3"), ("p", "F2"), ("Y", "F2"), ("M", "F1"), ("S", "F5"),
              ("I", "VHI"), ("Y", "VHI"), ("N", "VHW"), ("N", "ED"), ("I", "ED"),
              ("F1", "Q"), ("F2", "Q"), ("F3", "Q"), ("F4", "Q"), ("F5", "Q"), ("VHI", "Q"), ("VHW", "Q"), ("ED", "Q"),
              ("Q", "SEG")],
    "inputs": {"I": "monthlyIncome", "E": "monthlyExpenses", "P": "monthlyDebtPayment", "D": "totalDebt",
               "C": "cashReserve", "V": "investmentAmount", "S": "impatienceLevel"},
    "factors": {"F1": "CashReserveMonths", "F2": "DebtToIncomeRatio", "F3": "SavingsRate", "F4": "ExpenseRatio",
                "F5": "Impatience"},
}
FLOW_V3 = {
    "name": "v3", "keys": V3_KEYS, "viewBox": "0 -18 1430 500", "minWidth": 900,
    "columns": [(10, "Girdiler"), (160, "Ara değişkenler"), (1080, "Faktörler (doğrusal, hepsi × κ)"), (1295, "Skor")],
    "nodes": [
        ("I", 10, 12, 120, 46, "Aylık gelir I", ["I > 0"], "in"),
        ("E", 10, 72, 120, 46, "Aylık gider E", ["E ≥ 0"], "in"),
        ("P", 10, 132, 120, 46, "Aylık taksit P", ["P ≥ 0"], "in"),
        ("C", 10, 192, 120, 46, "Nakit C", ["C ≥ 0"], "in"),
        ("V", 10, 252, 120, 46, "Yatırım V", ["V ≥ 0"], "in"),
        ("D", 10, 312, 120, 46, "Toplam borç D", ["D ≥ 0"], "in"),
        ("K", 10, 430, 120, 46, "Sabırsızlık K", ["1 … 5 (öz-beyan)"], "in"),
        ("Eeff", 160, 40, 150, 46, "Gider tabanı", ["Eeff = max(E; 0,1·I)"], "mid"),
        ("L", 160, 222, 150, 46, "Likit varlık", ["L = C + 0,5·V"], "mid"),
        ("O", 335, 100, 145, 46, "Aylık çıkış", ["O = Eeff + P"], "mid"),
        ("W", 335, 312, 145, 46, "Likit net servet", ["W = L − D"], "mid"),
        ("m", 510, 40, 160, 46, "Rezerv (ay)", ["m = L / O"], "mid"),
        ("X", 510, 180, 160, 46, "Fon hedefi üstü", ["X = max(0; L − 6·O)"], "mid"),
        ("lam", 510, 330, 160, 62, "Servet pisti λ", ["R = W⁺ / (12·Eeff) yıl", "λ = min(R / 25; 1)"], "mid"),
        ("N", 695, 240, 150, 46, "Net borç", ["N = max(0; D − X)"], "mid"),
        ("s", 875, 92, 180, 46, "Tasarruf oranı", ["s = (I − Eeff − Peff) / I"], "mid"),
        ("r", 875, 172, 180, 62, "Taksit oranı", ["r = Peff / I", "Peff = max(P; 0,035·N)"], "mid"),
        ("yv", 875, 262, 180, 62, "Net borç (yıl), tavan", ["y = N / 12I", "κ: y 5 → 1, 15 → 0"], "mid"),
        ("Res", 1080, 12, 190, 46, "Acil durum fonu · 30", ["m: 0 / 3 / 6 ay → 0 / 0,6 / 1"], "factor"),
        ("Sav", 1080, 92, 190, 46, "Tasarruf · 30", ["max(s: −%10/0/10/20; λ)"], "factor"),
        ("Inst", 1080, 172, 190, 46, "Taksit oranı · 25", ["max(r: %10/20/36/50; λ)"], "factor"),
        ("ND", 1080, 262, 190, 46, "Net borç · 10", ["y: 0,5 / 1 / 3 / 5 yıl"], "factor"),
        ("Imp", 1080, 430, 190, 46, "Sabırsızlık · 5", ["K = 1…5 → 1/0,8/0,6/0,2/0"], "factor"),
        ("Q", 1295, 196, 125, 78, "Skor", ["Σ yuvarla(maks ×", "pay × κ);", "kural yok"], "out"),
        ("SEG", 1295, 310, 125, 78, "Segment", ["0–40 LOW", "41–70 MEDIUM", "71–100 HIGH"], "out"),
    ],
    "edges": [("I", "Eeff"), ("E", "Eeff"), ("C", "L"), ("V", "L"), ("Eeff", "O"), ("P", "O"), ("L", "W"), ("D", "W"),
              ("L", "m"), ("O", "m"), ("L", "X"), ("O", "X"), ("W", "lam"), ("Eeff", "lam"), ("D", "N"), ("X", "N"),
              ("I", "s"), ("Eeff", "s"), ("P", "s"), ("N", "s"), ("P", "r"), ("N", "r"), ("I", "r"), ("N", "yv"),
              ("I", "yv"), ("m", "Res"), ("s", "Sav"), ("lam", "Sav"), ("r", "Inst"), ("lam", "Inst"), ("yv", "ND"),
              ("yv", "Res", "cap"), ("yv", "Sav", "cap"), ("yv", "Inst", "cap"), ("yv", "Imp", "cap"), ("K", "Imp"),
              ("Res", "Q"), ("Sav", "Q"), ("Inst", "Q"), ("ND", "Q"), ("Imp", "Q"), ("Q", "SEG")],
    "inputs": {"I": "monthlyIncome", "E": "monthlyExpenses", "P": "monthlyDebtPayment", "D": "totalDebt",
               "C": "cashReserve", "V": "investmentAmount", "K": "impatienceLevel"},
    "factors": {"Res": "CashReserveMonths", "Inst": "InstallmentToIncome", "ND": "NetDebtToIncome", "Sav": "SavingsRate",
                "Imp": "Impatience"},
}
FLOWS = [FLOW_V2, FLOW_V3]


def flow_closure(spec: dict, skip_cap: bool = False) -> tuple[dict, dict]:
    down, up = defaultdict(set), defaultdict(set)
    for a, b, *kind in spec["edges"]:
        if skip_cap and kind:
            continue
        down[a].add(b)
        up[b].add(a)

    def reach(start, graph):
        seen, stack = set(), [start]
        while stack:
            for nxt in graph[stack.pop()]:
                if nxt not in seen:
                    seen.add(nxt)
                    stack.append(nxt)
        return seen

    return {n[0]: reach(n[0], down) for n in spec["nodes"]}, {n[0]: reach(n[0], up) for n in spec["nodes"]}


def flow_svg(spec: dict) -> str:
    down, up = flow_closure(spec)
    nodes = {n[0]: n for n in spec["nodes"]}
    pre = spec["name"]
    parts = [f'<svg class="flow-svg" viewBox="{spec["viewBox"]}" style="min-width:{spec["minWidth"]}px" role="group" '
             f'aria-label="{esc(spec["name"])}: girdilerden skora akış şeması">']
    for i, (a, b, *kind) in enumerate(spec["edges"]):
        na, nb = nodes[a], nodes[b]
        if na[1] == nb[1]:  # same column (score -> segment): straight down
            x = na[1] + na[3] / 2
            d = f"M{x},{na[2] + na[4]} V{nb[2]}"
        else:
            sx, sy = na[1] + na[3], na[2] + na[4] / 2
            tx, ty = nb[1], nb[2] + nb[4] / 2
            dx = (tx - sx) / 2
            d = f"M{sx},{sy} C{sx + dx},{sy} {tx - dx},{ty} {tx},{ty}"
        parts.append(f'<path class="edge" id="{pre}e{i}" d="{d}"/>')
    for nid, x, y, w, h, title, lines, kind in spec["nodes"]:
        related = {nid} | down[nid] | up[nid]
        on_edges = [f"{pre}e{i}" for i, (a, b, *_k) in enumerate(spec["edges"])
                    if (a in up[nid] | {nid} and b in up[nid] | {nid}) or (a in down[nid] | {nid} and b in down[nid] | {nid})]
        label = f"{title}: {'; '.join(lines)}"
        parts.append(f'<g class="node {kind}" tabindex="0" role="button" aria-label="{esc(label)}" '
                     f'data-on="{" ".join(sorted(related))}" data-edges="{" ".join(on_edges)}" data-id="{nid}">'
                     f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="6"/>'
                     f'<text x="{x + 10}" y="{y + 19}" class="t">{esc(title)}</text>')
        for k, line in enumerate(lines):
            parts.append(f'<text x="{x + 10}" y="{y + 36 + 15 * k}" class="f">{esc(line)}</text>')
        parts.append("</g>")
    for x, text in spec["columns"]:
        parts.append(f'<text x="{x}" y="-15" class="col">{esc(text)}</text>')
    parts.append("</svg>")
    return "".join(parts)


def flow_touches(spec: dict) -> dict[str, set[str]]:
    """Factors each input reaches in the diagram, cap edges left out (to check it against the measured matrix)."""
    down, _ = flow_closure(spec, skip_cap=True)
    return {spec["inputs"][i]: {spec["factors"][n] for n in down[i] if n in spec["factors"]} for i in spec["inputs"]}


# --- analysis ---------------------------------------------------------------------------------------------------------
class Model:
    def __init__(self, scorers: list[Scorer], seed: int, sobol_n: int, bootstrap: int):
        self.scorers, self.seed, self.sobol_n, self.bootstrap = scorers, seed, sobol_n, bootstrap
        self.batch = Batch()
        self.r1: dict[str, list[Res | None]] = {}
        self.r2: dict[str, list[Res | None]] = {}
        self.r3: dict[str, list[Res | None]] = {}
        self.rules: list[str] = []
        self.factor_keys: dict[str, list[str]] = {}
        self.factor_max: dict[str, dict[str, int]] = {}

    # ---- pass 1 ----
    def build_pass1(self) -> None:
        b = self.batch
        self.personas = b.add([p for *_, p in PERSONAS])
        self.sweeps = {}
        for key, *_rest, p in PERSONAS:
            for k in KEYS:
                xs = sweep_values(p, k)
                self.sweeps[(key, k)] = (xs, b.add([changed(p, **{k: x}) for x in xs]))
        self.cheap = {}
        for key, *_rest, p in PERSONAS:
            for k in MONEY:
                vals = cheapest_values(p, k)
                self.cheap[(key, k)] = (vals, b.add([changed(p, **{k: v}) for v in vals]))
            levels = list(range(p["impatienceLevel"] - 1, 0, -1))
            self.cheap[(key, "impatienceLevel")] = (levels, b.add([changed(p, impatienceLevel=s) for s in levels]))

        rng = random.Random(self.seed)
        n, d = self.sobol_n, len(KEYS)
        ua = [[rng.random() for _ in range(d)] for _ in range(n)]
        ub = [[rng.random() for _ in range(d)] for _ in range(n)]
        self.pop_a = [population_profile(u) for u in ua]
        self.pop_b = [population_profile(u) for u in ub]
        self.range_a, self.range_b = b.add(self.pop_a), b.add(self.pop_b)
        self.range_ab = [b.add([population_profile(ua[j][:i] + [ub[j][i]] + ua[j][i + 1:]) for j in range(n)])
                         for i in range(d)]

        # cliffs: +-1% of every money input (and +-1 impatience level) around every A and B profile
        self.pop = self.pop_a + self.pop_b
        self.cliff = []  # (profile index, input, direction, batch index)
        perturbed = []
        for j, p in enumerate(self.pop):
            for k in MONEY:
                if p[k] <= 0:
                    continue
                for sign in (-1, 1):
                    value = round(p[k] * (1 + 0.01 * sign), 2)
                    if k == "monthlyIncome" and value <= 0:
                        continue
                    self.cliff.append((j, k, sign, len(perturbed)))
                    perturbed.append(changed(p, **{k: value}))
            for sign in (-1, 1):
                level = p["impatienceLevel"] + sign
                if 1 <= level <= 5:
                    self.cliff.append((j, "impatienceLevel", sign, len(perturbed)))
                    perturbed.append(changed(p, impatienceLevel=level))
        self.range_cliff = b.add(perturbed)

        # dependency probes: halve / raise by 50% (+ half a month of income, so zero values move too)
        self.dep = []
        probes = []
        # a wide sample with debt and installment drawn independently, so structural links show even where the
        # realistic population (installment derived from the debt) never exercises them
        wide_rng = random.Random(self.seed + 2)
        self.wide = [wide_profile([wide_rng.random() for _ in KEYS]) for _ in range(600)]
        self.range_wide = b.add(self.wide)
        for j, p in enumerate(self.wide):
            for k in KEYS:
                if k == "impatienceLevel":
                    variants = [(p[k] % 5) + 1, ((p[k] + 2) % 5) + 1]
                else:
                    variants = [round(p[k] * 0.5, 2), round(p[k] * 1.5 + 0.5 * p["monthlyIncome"], 2)]
                for v in variants:
                    if v != p[k]:
                        self.dep.append((j, k, len(probes)))
                        probes.append(changed(p, **{k: v}))
        self.range_dep = b.add(probes)

        self.heats = [heat_savings_reserve(), heat_income_networth()]
        for h in self.heats:
            h["range"] = b.add(h["grid"])
        self.range_params = [b.add(list(pair)) for *_, pair in PARAMS]
        self.range_imp = b.add(IMPATIENCE_PROBES)
        self.range_params_v3 = [b.add(probes) for *_, probes in PARAMS_V3]
        self.range_wit = [b.add([w[2], w[3]]) for w in WITNESSES]

    def run_pass1(self) -> None:
        for s in self.scorers:
            res = s.score(self.batch.items, "pass1")
            self.r1[s.label] = res
            keys, maxima, declared = [], {}, None
            for r in res:
                if r is None:
                    continue
                if r.rule and r.rule not in self.rules:
                    self.rules.append(r.rule)
                declared = declared or r.maxima
                for f, pts in r.factors.items():
                    if f not in maxima:
                        keys.append(f)
                        maxima[f] = pts
                    maxima[f] = max(maxima[f], pts)
            if declared:  # the breakdown states its maximums: trust them over the observed ones
                keys, maxima = list(declared), dict(declared)
            self.factor_keys[s.label], self.factor_max[s.label] = keys, maxima
            s.version = next((r.version for r in res if r is not None), "?")
        self.rules.sort(key=lambda r: list(RULE_TR).index(r) if r in RULE_TR else 99)

    # ---- pass 2: refine the cliffs found in pass 1 ----
    def run_pass2(self) -> None:
        for s in self.scorers:
            res, keys = self.r1[s.label], self.factor_keys[s.label]
            batch = Batch()
            sweep_ref, cheap_ref = {}, {}
            for (pkey, k), (xs, rng_) in self.sweeps.items():
                if k == "impatienceLevel":
                    continue
                pts = [(x, res[i]) for x, i in zip(xs, rng_)]
                extra = []
                for (xa, ra), (xb, rb) in zip(pts, pts[1:]):
                    # refine real cliffs only: a piecewise-linear scorer moves 1 point per grid step all the time
                    if abs(ra.score - rb.score) >= 2 or ra.rule != rb.rule:
                        extra += gap_values(xa, xb)
                base = dict(next(p for key, *_r, p in PERSONAS if key == pkey))
                sweep_ref[(pkey, k)] = (extra, batch.add([changed(base, **{k: x}) for x in extra]))
            for (pkey, k), (vals, rng_) in self.cheap.items():
                base = next(p for key, *_r, p in PERSONAS if key == pkey)
                target = res[self.personas[[q[0] for q in PERSONAS].index(pkey)]].score + 10
                hit = next((n for n, i in enumerate(rng_) if res[i].score >= target), None)
                if k == "impatienceLevel" or hit is None:
                    continue
                prev = base[k] if hit == 0 else vals[hit - 1]
                # whole TL between the last miss and the first hit (all of them when the gap is <= 400 TL),
                # ordered from the smallest change to the largest
                sub = sorted(gap_values(min(prev, vals[hit]), max(prev, vals[hit]), 400), key=lambda v: abs(v - base[k]))
                cheap_ref[(pkey, k)] = (sub, batch.add([changed(base, **{k: v}) for v in sub]))
            self.r2[s.label] = s.score(batch.items, "pass2") if batch.items else []
            s.sweep_ref, s.cheap_ref = sweep_ref, cheap_ref

            # pass 3, +10 search only: every whole TL between the last miss and the first hit of pass 2
            batch3, cheap_ref3 = Batch(), {}
            for (pkey, k), (sub, rng2) in cheap_ref.items():
                base = next(p for key, *_r, p in PERSONAS if key == pkey)
                target = res[self.personas[[q[0] for q in PERSONAS].index(pkey)]].score + 10
                vals, rng1 = self.cheap[(pkey, k)]
                cands = sorted([(v, res[i]) for v, i in zip(vals, rng1)] + [(v, self.r2[s.label][i]) for v, i in zip(sub, rng2)],
                               key=lambda c: abs(c[0] - base[k]))
                hit = next((n for n, (_, r) in enumerate(cands) if r.score >= target), None)
                if hit is None:
                    continue
                prev = base[k] if hit == 0 else cands[hit - 1][0]
                extra = sorted(gap_values(min(prev, cands[hit][0]), max(prev, cands[hit][0]), 2000), key=lambda v: abs(v - base[k]))
                if extra:
                    cheap_ref3[(pkey, k)] = (extra, batch3.add([changed(base, **{k: v}) for v in extra]))
            self.r3[s.label] = s.score(batch3.items, "pass3") if batch3.items else []
            s.cheap_ref3 = cheap_ref3

    # ---- summaries ----
    def res_of(self, label: str, rng_) -> list[Res]:
        return [self.r1[label][i] for i in rng_]

    def persona_data(self) -> list[dict]:
        out = []
        for n, (key, label, desc, p) in enumerate(PERSONAS):
            item = {"key": key, "label": label, "description": desc, "profile": p, "results": {}}
            for s in self.scorers:
                r = self.r1[s.label][self.personas[n]]
                item["results"][s.label] = {"score": r.score, "segment": r.segment, "rule": r.rule,
                                            "factors": [r.factors.get(f) for f in self.factor_keys[s.label]],
                                            "warnings": list(r.warnings)}
            out.append(item)
        return out

    def sweep_data(self) -> dict:
        out = defaultdict(dict)
        for (pkey, k), (xs, rng_) in self.sweeps.items():
            item = {"lo": xs[0], "hi": xs[-1], "base": next(p for q, *_r, p in PERSONAS if q == pkey)[k],
                    "discrete": k == "impatienceLevel", "runs": {}}
            for s in self.scorers:
                pts = [(x, self.r1[s.label][i]) for x, i in zip(xs, rng_)]
                if (pkey, k) in s.sweep_ref:
                    extra, rng2 = s.sweep_ref[(pkey, k)]
                    pts += [(x, self.r2[s.label][i]) for x, i in zip(extra, rng2)]
                pts.sort(key=lambda t: t[0])
                item["runs"][s.label] = runs_of(pts, self.factor_keys[s.label], self.rules)
            out[pkey][k] = item
        return out

    def cheapest_data(self) -> dict:
        out = {}
        for s in self.scorers:
            per = {}
            for n, (pkey, *_r, p) in enumerate(PERSONAS):
                base = self.r1[s.label][self.personas[n]]
                target = base.score + 10
                rows = {}
                for k in KEYS:
                    vals, rng_ = self.cheap[(pkey, k)]
                    cands = list(zip(vals, (self.r1[s.label][i] for i in rng_)))
                    if (pkey, k) in s.cheap_ref:
                        sub, rng2 = s.cheap_ref[(pkey, k)]
                        cands += list(zip(sub, (self.r2[s.label][i] for i in rng2)))
                    if (pkey, k) in s.cheap_ref3:
                        sub, rng3 = s.cheap_ref3[(pkey, k)]
                        cands += list(zip(sub, (self.r3[s.label][i] for i in rng3)))
                    # every candidate lies on the favourable side, so the smallest change is the closest value
                    cands.sort(key=lambda c: abs(c[0] - p[k]))
                    found = next(((v, r) for v, r in cands if r.score >= target), None)
                    if target > 100:
                        rows[k] = {"status": "max"}
                    elif k == "impatienceLevel" and p[k] <= 1:
                        rows[k] = {"status": "lowest"}
                    elif k != "impatienceLevel" and FAVOURABLE[k] < 0 and p[k] <= 0:
                        rows[k] = {"status": "zero"}
                    elif found is None:
                        rows[k] = {"status": "none"}
                    else:
                        v, r = found
                        delta = v - p[k]
                        rows[k] = {"status": "ok", "value": v, "delta": delta,
                                   "rel": delta / p[k] if p[k] else None, "score": r.score, "rule": r.rule,
                                   "incomeMonths": abs(delta) / p["monthlyIncome"] if k != "impatienceLevel" else None}
                money = {k: v for k, v in rows.items() if k in MONEY and v["status"] == "ok" and v["rel"] is not None}
                best = min(money, key=lambda k: abs(money[k]["rel"])) if money else None
                per[pkey] = {"base": base.score, "target": target, "rows": rows, "best": best}
            out[s.label] = per
        return out

    def sobol_data(self) -> dict:
        out = {}
        n = self.sobol_n
        rng = random.Random(self.seed + 1)
        for s in self.scorers:
            ya = [r.score for r in self.res_of(s.label, self.range_a)]
            yb = [r.score for r in self.res_of(s.label, self.range_b)]
            yab = [[r.score for r in self.res_of(s.label, rg)] for rg in self.range_ab]
            first, total, var = sobol_indices(ya, yb, yab, list(range(n)))
            boots_f, boots_t = [[] for _ in KEYS], [[] for _ in KEYS]
            for _ in range(self.bootstrap):
                idx = [rng.randrange(n) for _ in range(n)]
                f, t, _v = sobol_indices(ya, yb, yab, idx)
                for i in range(len(KEYS)):
                    boots_f[i].append(f[i])
                    boots_t[i].append(t[i])

            def ci(values):
                values = sorted(values)
                return values[int(0.025 * len(values))], values[min(len(values) - 1, int(0.975 * len(values)))]

            rows = []
            for i, k in enumerate(KEYS):
                f_lo, f_hi = ci(boots_f[i])
                t_lo, t_hi = ci(boots_t[i])
                rows.append({"input": k, "S1": first[i], "S1lo": f_lo, "S1hi": f_hi, "ST": total[i], "STlo": t_lo, "SThi": t_hi})
            pop = self.res_of(s.label, self.range_a) + self.res_of(s.label, self.range_b)
            scores = [r.score for r in pop]
            mean = sum(scores) / len(scores)
            keys = self.factor_keys[s.label]
            shares = []
            for f in keys:
                pts = [r.factors.get(f, 0) for r in pop]
                fm = sum(pts) / len(pts)
                cov = sum((a - fm) * (b - mean) for a, b in zip(pts, scores)) / len(pts)
                shares.append({"factor": f, "max": self.factor_max[s.label][f], "mean": fm,
                               "effective": cov / var if var else 0.0})
            out[s.label] = {"rows": rows, "variance": var, "mean": mean, "sumS1": sum(first),
                            "warnings": dict(Counter(w for r in pop for w in r.warnings)),
                            "rules": dict(Counter(str(r.rule) for r in pop)), "segments": dict(Counter(r.segment for r in pop)),
                            "factorShares": shares, "evaluations": n * (len(KEYS) + 2)}
        return out

    def cliff_data(self) -> dict:
        out = {}
        for s in self.scorers:
            base = self.res_of(s.label, self.range_a) + self.res_of(s.label, self.range_b)
            pert = self.res_of(s.label, self.range_cliff)
            keys = self.factor_keys[s.label]
            max_abs = [0] * len(base)
            per_input = {k: {"profiles": set(), "moved": set(), "deltas": []} for k in KEYS}
            causes = Counter()
            cause_max = {}
            for j, k, sign, i in self.cliff:
                before, after = base[j], pert[i]
                delta = after.score - before.score
                per_input[k]["profiles"].add(j)
                if delta:
                    per_input[k]["moved"].add(j)
                    per_input[k]["deltas"].append(abs(delta))
                if k != "impatienceLevel":
                    max_abs[j] = max(max_abs[j], abs(delta))
                if delta and k != "impatienceLevel":
                    if before.rule != after.rule:
                        sig = f"kural: {before.rule or 'yok'} → {after.rule or 'yok'}"
                    else:
                        sig = " + ".join(f"{f} {before.factors.get(f)}→{after.factors.get(f)}" for f in keys
                                         if before.factors.get(f) != after.factors.get(f))
                    cid = (k, "+%1" if sign > 0 else "−%1", sig)
                    causes[cid] += 1
                    cause_max[cid] = max(cause_max.get(cid, 0), abs(delta))
            hist = Counter(max_abs)
            total = len(base)
            out[s.label] = {
                "profiles": total, "hist": sorted(hist.items()),
                "atLeast": {t: sum(c for v, c in hist.items() if v >= t) / total for t in (1, 5, 10, 20)},
                "max": max(max_abs),
                "perInput": {k: {"share": len(v["moved"]) / len(v["profiles"]) if v["profiles"] else 0.0,
                                 "tested": len(v["profiles"]),
                                 "meanAbs": sum(v["deltas"]) / len(v["deltas"]) if v["deltas"] else 0.0,
                                 "maxAbs": max(v["deltas"], default=0)} for k, v in per_input.items()},
                "causes": [{"input": k, "dir": d, "change": sig, "count": c, "maxAbs": cause_max[(k, d, sig)],
                            "label": self.step_label(sig)} for (k, d, sig), c in causes.most_common(14)],
                "causeTotal": sum(causes.values()),
            }
        return out

    @staticmethod
    def step_label(sig: str) -> str:
        if sig.startswith("kural:"):
            return "kural eşiği"
        labels = []
        for part in sig.split(" + "):
            name, _, move = part.rpartition(" ")
            try:
                a, b = (int(float(x)) for x in move.split("→"))
            except ValueError:  # a factor the other scorer does not have
                labels.append("?")
                continue
            labels.append(V2_STEPS.get((name, max(a, b), min(a, b)), "?"))
        return " + ".join(labels)

    def dep_data(self) -> dict:
        out = {}
        for s in self.scorers:
            base = self.res_of(s.label, self.range_wide)
            probes = self.res_of(s.label, self.range_dep)
            keys = self.factor_keys[s.label]
            count = defaultdict(lambda: defaultdict(int))
            clean, total = Counter(), Counter()
            for j, k, i in self.dep:
                before, after = base[j], probes[i]
                total[k] += 1
                count[k]["__score"] += before.score != after.score
                count[k]["__rule"] += before.rule != after.rule
                if before.rule not in OVERRIDE_RULES and after.rule not in OVERRIDE_RULES:
                    clean[k] += 1
                    for f in keys:
                        count[k][f] += before.factors.get(f) != after.factors.get(f)
            matrix = {}
            for k in KEYS:
                row = {f: count[k][f] / clean[k] if clean[k] else 0.0 for f in keys}
                row["__rule"] = count[k]["__rule"] / total[k]
                row["__score"] = count[k]["__score"] / total[k]
                row["__reach"] = sum(self.factor_max[s.label][f] for f in keys if count[k][f] > 0)
                row["__touched"] = [f for f in keys if count[k][f] > 0]
                matrix[k] = row
            out[s.label] = {"matrix": matrix, "probes": sum(total.values()), "clean": sum(clean.values()),
                            "base": len(self.wide)}
        return out

    def heat_data(self) -> list[dict]:
        out = []
        for h in self.heats:
            item = {k: h[k] for k in ("id", "xs", "ys", "xLabel", "yLabel", "xFmt", "yFmt", "xTicks", "yTicks", "fixed")}
            item["z"], item["rule"], item["factors"] = {}, {}, {}
            for s in self.scorers:
                res = self.res_of(s.label, h["range"])
                item["z"][s.label] = [r.score for r in res]
                item["rule"][s.label] = [self.rules.index(r.rule) if r.rule else -1 for r in res]
                item["factors"][s.label] = [[r.factors.get(f) for f in self.factor_keys[s.label]] for r in res]
            out.append(item)
        return out

    def param_data(self) -> dict:
        rows = []
        for (group, name, value, meaning, level, source, factor, pair), rng_ in zip(PARAMS, self.range_params):
            checks = {}
            for s in self.scorers:
                before, after = self.res_of(s.label, rng_)
                checks[s.label] = {"before": before.score, "after": after.score,
                                   "fBefore": before.factors.get(factor) if factor else None,
                                   "fAfter": after.factors.get(factor) if factor else None,
                                   "ruleBefore": before.rule, "ruleAfter": after.rule}
            rows.append({"group": group, "name": name, "value": value, "meaning": meaning, "level": level,
                         "source": source, "factor": factor, "checks": checks})
        imp = {s.label: [r.factors.get("Impatience") for r in self.res_of(s.label, self.range_imp)] for s in self.scorers}
        segments = {}
        for s in self.scorers:
            seen = defaultdict(list)
            for r in self.r1[s.label]:
                if r is not None:
                    seen[r.segment].append(r.score)
            segments[s.label] = {k: [min(v), max(v)] for k, v in seen.items()}
        v3rows = []
        for (group, name, value, level, source, factor, _probes), rng_ in zip(PARAMS_V3, self.range_params_v3):
            got = {}
            for s in self.scorers:
                res = self.res_of(s.label, rng_)
                has = factor is not None and factor in self.factor_keys[s.label]
                got[s.label] = {"values": [r.factors.get(factor) if has else r.score for r in res],
                                "what": FACTOR_TR.get(factor, factor) if has else "skor",
                                "max": self.factor_max[s.label].get(factor) if has else 100,
                                "rules": [r.rule for r in res], "warnings": [list(r.warnings) for r in res]}
            v3rows.append({"group": group, "name": name, "value": value, "level": level, "source": source,
                           "factor": factor, "got": got})
        return {"rows": rows, "v3rows": v3rows, "impatience": imp, "segments": segments,
                "maxima": {s.label: self.factor_max[s.label] for s in self.scorers}}

    def witness_data(self) -> list[dict]:
        out = []
        for (title, key, before, after, rule), rng_ in zip(WITNESSES, self.range_wit):
            item = {"title": title, "input": key, "before": before[key], "after": after[key], "ruleDriven": rule,
                    "profile": before, "results": {}}
            for s in self.scorers:
                a, b = self.res_of(s.label, rng_)
                item["results"][s.label] = {"before": a.score, "after": b.score, "delta": b.score - a.score,
                                            "ruleBefore": a.rule, "ruleAfter": b.rule}
            out.append(item)
        return out

    def check_flow(self, deps: dict) -> dict:
        """Each hand-drawn diagram against the scorer with the same factor keys: a factor the scorer measurably moves
        but the diagram does not reach is an error; a drawn path the sample never exercised is only a note."""
        out = {}
        for spec in FLOWS:
            scorer = next((s for s in self.scorers if self.factor_keys[s.label] == spec["keys"]), None)
            if scorer is None:
                continue
            drawn = flow_touches(spec)
            issues, notes = [], []
            for k in KEYS:
                measured = set(deps[scorer.label]["matrix"][k]["__touched"])
                if measured - drawn[k]:
                    issues.append(f"{INPUT_TR[k]}: şemada yok {sorted(measured - drawn[k])}")
                if drawn[k] - measured:
                    notes.append(f"{INPUT_TR[k]} → {', '.join(FACTOR_TR.get(f, f) for f in sorted(drawn[k] - measured))}")
            out[spec["name"]] = {"scorer": scorer.label, "issues": issues, "notes": notes}
        return out


# --- page sections (static HTML) --------------------------------------------------------------------------------------
LEVELS = {"güçlü": ("good", "✓"), "kısmi": ("warn", "◐"), "dayanaksız": ("crit", "✕"), "uzman görüşü": ("none", "○"),
          "yargı": ("none", "△")}


def badge(level: str) -> str:
    cls, icon = LEVELS[level]
    return f'<span class="lvl"><span class="ico {cls}" aria-hidden="true">{icon}</span>{esc(level)}</span>'


def table(head: list[str], rows: list[str], caption: str = "", cls: str = "") -> str:
    cap = f"<caption>{caption}</caption>" if caption else ""
    return (f'<div class="scroll"><table class="{cls}">{cap}<thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def details(summary: str, body: str) -> str:
    return f'<details class="tv"><summary>{esc(summary)}</summary>{body}</details>'


def legend(labels: list[str]) -> str:
    if len(labels) < 2:
        return ""
    return '<div class="legend">' + "".join(
        f'<span class="key"><span class="sw sw{i}"></span>{esc(l)}</span>' for i, l in enumerate(labels)) + "</div>"


def pair(blocks: list[str]) -> str:
    """Per-scorer blocks side by side on wide screens, stacked on narrow ones."""
    return blocks[0] if len(blocks) == 1 else '<div class="pair">' + "".join(f"<div>{b}</div>" for b in blocks) + "</div>"


def labels_with(m: dict, labels: list[str], keys: list[str]) -> list[str]:
    return [l for l in labels if m["factorKeys"][l] == keys]


def formulas_v2_html() -> str:
    return """
<div class="formula">
<p><b>Girdiler.</b> <var>I</var> aylık gelir (&gt; 0), <var>E</var> aylık gider, <var>P</var> aylık taksit, <var>D</var>
toplam borç, <var>C</var> nakit, <var>V</var> yatırım (hepsi TL, ≥ 0, üst sınır yok), <var>S</var> sabırsızlık
(1–5, öz-beyan).</p>
<p><b>Ara değişkenler.</b> net borç <var>N</var> = <var>D</var> − <var>C</var> − <var>V</var> (negatifse net servet
<var>W</var> = −<var>N</var>) · <var>Y</var> = max(<var>N</var>, 0) / (12·<var>I</var>) yıl · rezerv <var>R</var> =
<var>C</var> + 0,5·<var>V</var> · <var>M</var> = <var>R</var> / <var>E</var> ay (<var>E</var> = 0 iken <var>R</var> &gt; 0
→ 6, değilse 0) · <var>p</var> = <var>P</var>/<var>I</var> · <var>s</var> = (<var>I</var> − <var>E</var> − <var>P</var>)/<var>I</var>
· <var>e</var> = <var>E</var>/<var>I</var>. Dikkat: <var>s</var> = 1 − <var>e</var> − <var>p</var>.</p>
<p><b>Basamak fonksiyonları.</b><br>
F1 acil durum fonu = 25 [<var>M</var> ≥ 6], 15 [≥ 3], 8 [≥ 1], 0<br>
F2 borç yükü = min(g(<var>p</var>), h(<var>Y</var>)); g = 25 [<var>p</var> ≤ 0,10], 15 [≤ 0,20], 8 [≤ 0,36], 0;
h = 25 [<var>Y</var> ≤ 0,5], 15 [≤ 1], 8 [≤ 3], 0<br>
F3 tasarruf = 25 [<var>s</var> ≥ 0,20], 15 [≥ 0,10], 8 [≥ 0], 0<br>
F4 gider oranı = 15 [<var>e</var> ≤ 0,40], 9 [≤ 0,60], 5 [≤ 0,80], 0<br>
F5 sabırsızlık = 10, 8, 5, 2, 0 (<var>S</var> = 1 … 5)</p>
<p><b>Skor.</b> Q = F1 + F2 + F3 + F4 + F5 (0–100, tam sayı). Kurallar bu sırayla bakılır ve ilk uyan skoru belirler:
(1) <var>I</var> ≥ 1.000.000 ve <var>Y</var> ≤ 1 → 100; (2) <var>W</var> ≥ 10.000.000 → 100; (3) <var>I</var> &lt;
1.000.000 ve <var>N</var> ≥ 100.000.000 → 0. Kural uyunca faktörler tam (100) ya da 0 yazılır. <b>Segment:</b> LOW
0–40, MEDIUM 41–70, HIGH 71–100.</p>
</div>"""


def formulas_v3_html() -> str:
    return """
<div class="formula">
<p><b>Girdiler.</b> v2 ile aynı (<var>K</var> = sabırsızlık 1–5). Doğrulama da aynı; hiçbir girdi reddedilmiyor.</p>
<p><b>Ara değişkenler.</b> likit varlık <var>L</var> = <var>C</var> + 0,5·<var>V</var> · gider tabanı
<var>E</var>′ = max(<var>E</var>; 0,1·<var>I</var>) · aylık çıkış <var>O</var> = <var>E</var>′ + <var>P</var> ·
rezerv <var>m</var> = <var>L</var> / <var>O</var> ay · fon hedefi üstü <var>X</var> = max(0; <var>L</var> − 6·<var>O</var>) ·
net borç <var>N</var> = max(0; <var>D</var> − <var>X</var>) · <var>y</var> = <var>N</var> / (12·<var>I</var>) yıl ·
etkin taksit <var>P</var>′ = max(<var>P</var>; 0,035·<var>N</var>) · <var>r</var> = <var>P</var>′ / <var>I</var> ·
<var>s</var> = (<var>I</var> − <var>E</var>′ − <var>P</var>′) / <var>I</var> · likit net servet <var>W</var> = <var>L</var> − <var>D</var> ·
pist <var>R</var> = <var>W</var>⁺ / (12·<var>E</var>′) yıl.</p>
<p><b>Doğrusal paylar</b> (çapalar arasında doğrusal, dışında sabit): rezerv <var>m</var> 0 / 3 / 6 ay → 0 / 0,6 / 1 ·
taksit <var>r</var> %10 / 20 / 36 / 50 → 1 / 0,6 / 0,2 / 0 · net borç <var>y</var> 0,5 / 1 / 3 / 5 yıl → 1 / 0,6 / 0,2 / 0 ·
tasarruf <var>s</var> −%10 / 0 / 10 / 20 → 0 / 0,2 / 0,6 / 1 · sabırsızlık 1…5 → 1 / 0,8 / 0,6 / 0,2 / 0.
Servet pisti λ = min(<var>R</var> / 25; 1) taksit ve tasarruf paylarını en az λ'ya kaldırır. Ödeme gücü tavanı
κ: <var>y</var> 5 yıldan 15 yıla çıkarken 1'den 0'a iner ve <b>her</b> faktörü çarpar.</p>
<p><b>Skor.</b> faktör puanı = yuvarla(maks × pay × κ), yarım yukarı; maksimumlar acil fon 30, taksit oranı 25, net borç
10, tasarruf 30, sabırsızlık 5. Skor = faktörlerin toplamı; TL eşiği ve skoru belirleyen kural yok. <code>appliedRule</code>
yalnız etiket: κ &lt; 1 → SOLVENCY_CAP, pist skoru yükseltiyorsa → WEALTH_RUNWAY. Uyarı = puan: faktör maksimumunun
%60'ının altındaysa uyarısı çıkar. Segment sınırları v2 ile aynı (41 / 71).</p>
</div>"""


def one_tl_deltas(m: dict, label: str) -> list[int]:
    """|score change| over every probe pair that differs by 1-2 TL (witnesses and v2 threshold probes)."""
    out = [abs(w["results"][label]["delta"]) for w in m["witnesses"]]
    out += [abs(r["checks"][label]["after"] - r["checks"][label]["before"]) for r in m["params"]["rows"]]
    return out


def metric_rows(m: dict, labels: list[str]) -> list[tuple[str, dict, str]]:
    """(name, label -> display text, note) for the headline comparison."""
    rows = []

    def per(fn):
        return {l: fn(l) for l in labels}

    rows.append(("1–2 TL'lik sınama çiftlerinde en büyük |Δskor|", per(lambda l: str(max(one_tl_deltas(m, l)))),
                 f"{len(one_tl_deltas(m, labels[0]))} çift: eşik sınamaları ve elle kurulmuş uçurum örnekleri"))
    rows.append(("±%1 tek girdi: en büyük |Δskor|", per(lambda l: str(m["cliffs"][l]["max"])),
                 f"{num(m['cliffs'][labels[0]]['profiles'])} örnek profil × 6 parasal girdi"))
    rows.append(("±%1 ile skoru oynayan profil", per(lambda l: pct(m["cliffs"][l]["atLeast"][1])), "en az 1 puan"))
    rows.append(("±%1 ile skoru ≥ 5 puan oynayan profil", per(lambda l: pct(m["cliffs"][l]["atLeast"][5])), ""))
    rows.append(("Ortalama skor (örnek nüfus)", per(lambda l: num(m["sobol"][l]["mean"], 1)), "Sobol nüfusu, A ve B"))
    for seg in ("LOW", "MEDIUM", "HIGH"):
        rows.append((f"{seg} payı", per(lambda l, seg=seg: pct(m["sobol"][l]["segments"].get(seg, 0)
                                                              / sum(m["sobol"][l]["segments"].values()))), ""))
    for k in ("monthlyIncome", "impatienceLevel"):
        rows.append((f"Toplam Sobol indeksi: {SHORT_TR[k].lower()}",
                     per(lambda l, k=k: idx(next(r["ST"] for r in m["sobol"][l]["rows"] if r["input"] == k))),
                     "gelir: oranlar sabitken gelir düzeyinin etkisi" if k == "monthlyIncome" else "öz-beyan"))
    rows.append(("Sabırsızlık 5 → 1 kazancı", per(lambda l: str(m["params"]["impatience"][l][0] - m["params"]["impatience"][l][-1])),
                 "beyanın değeri, puan"))
    # how often v3's consistency mechanisms fire in this (independently sampled) population, read from its warnings
    for warning, name, note in (
            ("Installment below interest", "Faiz tabanı bağlıyor (taksit < net borcun %3,5'i)",
             "taksit borçtan ve çekilen vadeden türetildi; öneri belgesindeki kalibre nüfusta %17,1"),
            ("Installment without debt", "Taksit var, borç yok", "veri kalitesi uyarısı; örnekte bilerek %4,4"),
            ("Extreme total debt", "Tavan devrede (net borç > 5 yıllık gelir)", "v2'de: net borç ≥ 100 Mn kuralı")):
        if any(warning in m["sobol"][l]["warnings"] for l in labels):
            rows.append((name, per(lambda l, w=warning: pct(m["sobol"][l]["warnings"].get(w, 0)
                                                           / sum(m["sobol"][l]["segments"].values()))
                                   if w in m["sobol"][l]["warnings"] or m["factorKeys"][l] == V3_KEYS else "—"), note))
    return rows


def tiles_html(m: dict, labels: list[str]) -> str:
    byname = {name: vals for name, vals, _ in metric_rows(m, labels)}
    picks = [("1–2 TL'lik sınama çiftlerinde en büyük |Δskor|", "1 TL ile en büyük skor sıçraması"),
             ("±%1 tek girdi: en büyük |Δskor|", "±%1 tek girdi değişikliğinde en büyük sıçrama"),
             ("±%1 ile skoru ≥ 5 puan oynayan profil", "±%1'lik değişiklikle skoru ≥ 5 puan oynayan profil"),
             ("Toplam Sobol indeksi: gelir", "gelir düzeyinin toplam Sobol indeksi (oranlar sabit)"),
             ("Toplam Sobol indeksi: sabırsızlık", "sabırsızlığın (öz-beyan) toplam Sobol indeksi"),
             ("Sabırsızlık 5 → 1 kazancı", "beyanı 5'ten 1'e çekmenin kazancı (puan)")]
    sep = " → "
    hint = sep.join(labels) if len(labels) > 1 else ""
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="big">{esc(sep.join(byname[k][l] for l in labels))}</div><div>{esc(text)}</div>'
        f'<div class="hint">{esc(hint)}</div></div>' for k, text in picks) + "</div>"


def summary_html(m: dict, labels: list[str]) -> str:
    head = ["Ölçü"] + [esc(l) for l in labels] + ["Not"]
    rows = [f"<tr><th>{esc(n)}</th>" + "".join(f"<td class='n'>{esc(v[l])}</td>" for l in labels)
            + f"<td class='hint'>{esc(note)}</td></tr>" for n, v, note in metric_rows(m, labels)]
    metrics = table(head, rows, "Hepsi aynı profillerin iki puanlayıcıyla skorlanmasından.")

    sob_head = ["Girdi"] + [f"{esc(l)} S<sub>i</sub> · <b>S<sub>Ti</sub></b>" for l in labels]
    order = sorted(KEYS, key=lambda k: -next(r["ST"] for r in m["sobol"][labels[-1]]["rows"] if r["input"] == k))
    sob_rows = []
    for k in order:
        cells = "".join(f"<td class='n'>{idx(r['S1'])} · <b>{idx(r['ST'])}</b></td>"
                        for l in labels for r in [next(x for x in m["sobol"][l]["rows"] if x["input"] == k)])
        sob_rows.append(f"<tr><th>{esc(SOBOL_TR[k])}</th>{cells}</tr>")
    sobol = table(sob_head, sob_rows, "Birinci derece · toplam Sobol indeksi; ayrıntı ve aralıklar bölüm 7'de.")

    factors = []
    for l in labels:
        for f in m["factorKeys"][l]:
            if f not in factors:
                factors.append(f)
    w_rows = []
    for f in factors:
        cells = []
        for l in labels:
            share = next((x for x in m["sobol"][l]["factorShares"] if x["factor"] == f), None)
            if share is None:
                cells.append("<td class='n hint'>yok</td>")
            else:
                total = sum(x["max"] for x in m["sobol"][l]["factorShares"])
                cells.append(f"<td class='n'>{pct(share['effective'])} <span class='hint'>(nominal {pct(share['max'] / total, 0)})</span></td>")
        w_rows.append(f"<tr><th>{esc(FACTOR_TR.get(f, f))}</th>{''.join(cells)}</tr>")
    weights = table(["Faktör"] + [f"{esc(l)}: etkin ağırlık" for l in labels], w_rows,
                    "Etkin ağırlık = skor varyansının o faktörden gelen payı (bölüm 2).")

    p_rows = []
    for n, (pkey, plabel, *_r) in enumerate(PERSONAS):
        cells = []
        for l in labels:
            res = m["personas"][n]["results"][l]
            c = m["cheapest"][l][pkey]
            if c["target"] > 100:
                best = "skor 90'ın üstünde"
            elif c["best"]:
                r = c["rows"][c["best"]]
                best = f"{SHORT_TR[c['best']]} {signed(r['delta'])} TL ({pct(abs(r['rel']))}) → {r['score']}"
            else:
                best = "parasal yol yok"
            rule = f" · {res['rule']}" if res["rule"] else ""
            cells.append(f"<td class='n'><b>{res['score']}</b> <span class='hint'>{res['segment']}{esc(rule)}</span></td>"
                         f"<td>{esc(best)}</td>")
        p_rows.append(f"<tr><th>{esc(plabel)}</th>{''.join(cells)}</tr>")
    p_head = ["Kişi"]
    for l in labels:
        p_head += [f"Skor ({esc(l)})", f"En ucuz +10 ({esc(l)})"]
    personas = table(p_head, p_rows, "En ucuz +10: yüzde olarak en küçük tek parasal değişiklik (bölüm 8).")
    return (f"<h3>Ölçüler</h3>{metrics}<h3>Sobol indeksleri</h3>{sobol}<h3>Etkin ağırlıklar</h3>{weights}"
            f"<h3>Demo kişileri</h3>{personas}")


def deps_html(m: dict, labels: list[str]) -> str:
    parts = []
    for label in labels:
        d = m["deps"][label]
        keys = m["factorKeys"][label]
        maxima = m["factorMax"][label]

        def cell(v: float) -> str:
            if v <= 0:
                return '<td class="n mx m0" data-tip="0\nhiç değişmedi">—</td>'
            b = 1 if v <= 0.10 else 2 if v <= 0.40 else 3 if v <= 0.80 else 4
            return f'<td class="n mx m{b}" data-tip="{pct(v)}\nsınamaların bu payında faktör puanı değişti">{pct(v, 0) if v >= 0.005 else "<%1"}</td>'

        rows = []
        for k in KEYS:
            r = d["matrix"][k]
            rows.append(f"<tr><th>{esc(INPUT_TR[k])}</th>{''.join(cell(r[f]) for f in keys)}{cell(r['__rule'])}"
                        f"<td class='n'><b>{num(r['__reach'])}</b> <span class='hint'>/ {len(r['__touched'])}</span></td></tr>")
        head = ["Girdi"] + [f"{esc(FACTOR_TR.get(f, f))}<br><span class='hint'>{maxima[f]} puan</span>" for f in keys] + \
               ["Kural<br><span class='hint'>değişti</span>", "Ulaştığı<br><span class='hint'>puan</span>"]
        title = f"<h3>{esc(label)}</h3>" if len(labels) > 1 else ""
        parts.append(title + table(head, rows,
                     f"Geniş bir örnekte (borç ve taksit ayrı çekildi; {num(d['base'])} profil) her girdi yarıya indirildi ve 1,5 katına (+ yarım aylık gelir) "
                     f"çıkarıldı: {num(d['probes'])} sınama. Faktör sütunları, skoru bir kuralın belirlediği (v2) ya da "
                     f"tavanın ölçeklediği (v3) durumlar dışındaki {num(d['clean'])} sınamadan; “—” = hiç değişmedi.",
                     "matrix"))
    return pair(parts)


def weights_html(m: dict, labels: list[str]) -> str:
    parts = []
    for label in labels:
        sob = m["sobol"][label]
        total_max = sum(f["max"] for f in sob["factorShares"])
        rows = []
        for f in sob["factorShares"]:
            nominal = f["max"] / total_max
            rows.append(f"<tr><th>{esc(FACTOR_TR.get(f['factor'], f['factor']))}</th><td class='n'>{f['max']}</td>"
                        f"{bar_cell(f['effective'], 0.5)}<td class='n'>{num(f['effective'] / nominal, 2)}</td>"
                        f"<td class='n'>{num(f['mean'], 1)}</td></tr>")
        title = f"<h3>{esc(label)}</h3>" if len(labels) > 1 else ""
        parts.append(title + table(["Faktör", "Maks (nominal)", "Etkin ağırlık", "Etkin / nominal", "Ort. puan"], rows,
                                   f"Etkin ağırlık = cov(faktör, skor) / var(skor), Sobol nüfusunun A ve B örneklerinde "
                                   f"({num(2 * m['sobolN'])} profil); toplamı 1. Nüfus dağılımına bağlıdır."))
    return pair(parts)


def bar_cell(value: float, scale: float = 1.0) -> str:
    width = max(0.0, min(1.0, value / scale)) * 100
    return (f'<td class="n" data-tip="{pct(value)}"><span class="v">{pct(value)}</span>'
            f'<span class="track"><span class="fill" style="width:{width:.1f}%"></span></span></td>')


def params_html(m: dict, labels: list[str]) -> str:
    """v2's thresholds; every scorer is probed at the same profiles (v3 shows what a v2 cliff becomes there)."""
    data = m["params"]
    rows = []
    for r in data["rows"]:
        checks = []
        for label in labels:
            c = r["checks"][label]
            if r["factor"] and r["factor"] in m["factorKeys"][label]:
                fa, fb = c["fBefore"], c["fAfter"]
                text = f"{FACTOR_TR.get(r['factor'], r['factor'])}: {fa} → {fb}"
            elif r["factor"]:
                text = "bu faktör yok"
            else:
                text = f"kural: {c['ruleBefore'] or 'yok'} → {c['ruleAfter'] or 'yok'}"
            checks.append(f"<td class='chk'>{esc(text)}<div class='hint'>skor {c['before']} → {c['after']}</div></td>")
        meaning = f"<div class='hint'>{esc(r['meaning'])}</div>" if r["meaning"] else ""
        rows.append(f"<tr><td class='hint'>{esc(r['group'])}</td><th>{esc(r['name'])}{meaning}</th><td>{esc(r['value'])}</td>"
                    f"<td>{badge(r['level'])}</td><td class='wide'>{esc(r['source'])}</td>{''.join(checks)}</tr>")
    imp_cells = "".join(f"<td class='chk'>{' / '.join(str(v) for v in data['impatience'][l])}"
                        f"<div class='hint'>S = 1 … 5</div></td>" for l in labels)
    rows.append(f"<tr><td class='hint'>Sabırsızlık (10)</td><th>Sabırsızlık → puan<div class='hint'>tek maddelik öz-beyan; "
                f"öz-algı göstergesi</div></th><td>10 / 8 / 5 / 2 / 0</td><td>{badge('dayanaksız')}</td>"
                f"<td class='wide'>kaynak yok</td>{imp_cells}</tr>")
    max_cells = "".join(f"<td class='chk'>{' / '.join(str(v) for v in data['maxima'][l].values())}"
                        f"<div class='hint'>faktör maksimumları</div></td>" for l in labels)
    rows.append(f"<tr><td class='hint'>Ağırlıklar</td><th>Faktör ağırlıkları</th><td>25 / 25 / 25 / 15 / 10</td>"
                f"<td>{badge('uzman görüşü')}</td><td class='wide'>ekip kararı</td>{max_cells}</tr>")
    for seg, value, level, source in (
            ("MEDIUM", "LOW ≤ 40 < MEDIUM", "kısmi", "FinHealth: 40 altı kırılgan (sınır uyumlu)"),
            ("HIGH", "HIGH ≥ 71", "dayanaksız", "FinHealth'te sağlıklı ≥ 80; 71 daha cömert")):
        cells = "".join(f"<td class='chk'>{seg} en düşük {data['segments'][l].get(seg, ['–'])[0]}"
                        f"<div class='hint'>gözlenen skorlardan</div></td>" for l in labels)
        rows.append(f"<tr><td class='hint'>Segment</td><th>{esc(seg)} sınırı</th><td>{esc(value)}</td><td>{badge(level)}</td>"
                    f"<td class='wide'>{esc(source)}</td>{cells}</tr>")
    head = ["Grup", "Parametre", "Değer", "Dayanak", "Kaynak"] + [f"Sınama ({esc(l)})<br><span class='hint'>eşikte → 1 TL ötesi</span>"
                                                                   for l in labels]
    counts = Counter(r["level"] for r in data["rows"])
    other = f" Öteki sütunlar aynı profilleri öteki puanlayıcıyla gösterir." if len(labels) > 1 else ""
    return table(head, rows,
                 f"Her v2 eşiği iki profille sınandı: biri tam eşikte, diğeri 1 TL ötesinde (diğer faktörler eşiklerden uzak).{other} "
                 f"Dayanak düzeyleri ekibin YÖK/literatür araştırmasından: {counts['güçlü']} güçlü, {counts['kısmi']} kısmi, "
                 f"{counts['dayanaksız']} dayanaksız (+ sabırsızlık eşlemesi, ağırlıklar ve segmentler).", "params")


def params_v3_html(m: dict, labels: list[str]) -> str:
    data = m["params"]
    rows = []
    for r in data["v3rows"]:
        cells = []
        for l in labels:
            g = r["got"][l]
            vals = " / ".join("–" if v is None else str(v) for v in g["values"])
            rule = next((x for x in g["rules"] if x), None)
            hint = f"{g['what']}" + (f" / {g['max']}" if g["what"] != "skor" else "") + (f" · {rule}" if rule else "")
            if len(g["warnings"]) > 1:  # a warning only the first probe raises explains the mechanism (floor, data quality)
                only_first = [w for w in g["warnings"][0] if w not in g["warnings"][-1]]
                if only_first:
                    hint += " · ilkinde uyarı: " + ", ".join(only_first)
            cells.append(f"<td class='chk'><b>{esc(vals)}</b><div class='hint'>{esc(hint)}</div></td>")
        rows.append(f"<tr><td class='hint'>{esc(r['group'])}</td><th>{esc(r['name'])}</th><td>{esc(r['value'])}</td>"
                    f"<td>{badge(r['level'])}</td><td class='wide'>{esc(r['source'])}</td>{''.join(cells)}</tr>")
    v3 = labels_with(m, labels, V3_KEYS)
    if v3:
        maxima = data["maxima"][v3[0]]
        cells = "".join(f"<td class='chk'><b>{' / '.join(str(v) for v in data['maxima'][l].values())}</b>"
                        f"<div class='hint'>faktör maksimumları</div></td>" for l in labels)
        rows.append(f"<tr><td class='hint'>Ağırlıklar</td><th>Faktör maksimumları<div class='hint'>"
                    f"{esc(' / '.join(FACTOR_TR.get(f, f) for f in maxima))}</div></th><td>30 / 25 / 10 / 30 / 5</td>"
                    f"<td>{badge('uzman görüşü')}</td><td class='wide'>kanıt gücüne göre (öneri, bölüm 7)</td>{cells}</tr>")
    head = ["Grup", "Çapa / mekanizma", "Pay", "Dayanak", "Kaynak"] + [f"Ölçülen ({esc(l)})" for l in labels]
    counts = Counter(r["level"] for r in data["v3rows"])
    return table(head, rows,
                 "Her satırdaki profil tam çapanın üstünde; değer puanlayıcının o faktöre verdiği puan (birden çok profil "
                 "“/” ile). Doğrusal tabloda pay × maksimum = puan (ör. 0,6 × 30 = 18). v2 sütunu aynı profillerin v2 "
                 f"puanıdır. Dayanak (öneri belgesi, bölüm 8.3): {counts['güçlü']} güçlü, {counts['kısmi']} kısmi, "
                 f"{counts['dayanaksız']} dayanaksız, {counts['yargı']} gerekçeli yargı.", "params")


def cliffs_html(m: dict, labels: list[str]) -> str:
    cl = m["cliffs"]
    values = sorted({v for l in labels for v, _ in cl[l]["hist"] if v > 0})
    peak = max((c / cl[l]["profiles"] for l in labels for v, c in cl[l]["hist"] if v > 0), default=1.0)
    still = " · ".join(f"{esc(l) + ': ' if len(labels) > 1 else ''}{pct(dict(cl[l]['hist']).get(0, 0) / cl[l]['profiles'])}"
                       for l in labels)
    rows = []
    for v in values:
        bars = []
        for i, l in enumerate(labels):
            c = dict(cl[l]["hist"]).get(v, 0)
            share = c / cl[l]["profiles"]
            w = share / peak * 100
            bars.append(f'<div class="hb" tabindex="0" data-tip="{pct(share)}\n{esc(l)}: {num(c)} profil, en büyük |Δ| = {v}">'
                        f'<span class="hbar sw{i}" style="width:{w:.2f}%"></span><span class="hv">{pct(share)}</span></div>')
        rows.append(f'<div class="hrow"><div class="hl">{v} puan</div><div class="hbars">{"".join(bars)}</div></div>')
    chart = (f"<p>Profillerin <b>{still}</b>'inde hiçbir ±%1 değişiklik skoru oynatmıyor. Aşağıda kalanların en büyük "
             f"|Δskor| değeri; çubuk uzunluğu tüm profillere oranı.</p>" + legend(labels)
             + f'<div class="hchart" role="img" aria-label="En büyük skor değişiminin dağılımı">{"".join(rows)}</div>')
    tv_rows = [f"<tr><th>{v}</th>" + "".join(f"<td class='n'>{num(dict(cl[l]['hist']).get(v, 0))} "
                                            f"({pct(dict(cl[l]['hist']).get(v, 0) / cl[l]['profiles'])})</td>" for l in labels)
               + "</tr>" for v in [0] + values]
    chart += details("Tablo görünümü", table(["En büyük |Δskor|"] + [f"{esc(l)}: profil" for l in labels], tv_rows))

    first = labels[0]
    inp_rows = []
    for k in KEYS:
        cells = "".join(f"{bar_cell(cl[l]['perInput'][k]['share'])}<td class='n'>{num(cl[l]['perInput'][k]['meanAbs'], 1)}</td>"
                        f"<td class='n'>{cl[l]['perInput'][k]['maxAbs']}</td>" for l in labels)
        unit = "±1 seviye" if k == "impatienceLevel" else "±%1"
        inp_rows.append(f"<tr><th>{esc(INPUT_TR[k])} <span class='hint'>{unit}</span></th>{cells}</tr>")
    head = ["Girdi"]
    for l in labels:
        suffix = f" ({esc(l)})" if len(labels) > 1 else ""
        head += [f"Skoru oynattığı profil{suffix}", f"Ort. |Δ| (oynayınca){suffix}", f"En büyük |Δ|{suffix}"]
    per_input = table(head, inp_rows, "Pay = sıfır olmayan değerli profillerden ±%1 değişikliğin skoru değiştirdiği oran. "
                      "Sabırsızlık kesikli olduğu için ±1 seviye denendi ve üstteki dağılıma katılmadı.")

    blocks = []
    for l in labels:
        stepped = m["factorKeys"][l] == V2_KEYS
        cause_rows = []
        for c in cl[l]["causes"][:10]:
            change = c["change"]
            for f, name in FACTOR_TR.items():
                change = change.replace(f + " ", name + " ")
            label_cell = f"<td>{esc(c['label'])}</td>" if stepped else ""
            cause_rows.append(f"<tr><th>{esc(SHORT_TR[c['input']])} {esc(c['dir'])}</th><td>{esc(change)}</td>"
                              f"{label_cell}<td class='n'>{num(c['count'])}</td><td class='n'>{c['maxAbs']}</td></tr>")
        head = ["Değişiklik", "Ne değişti"] + (["Eşik"] if stepped else []) + ["Kaç kez", "En büyük |Δ|"]
        title = f"<h3>{esc(l)}</h3>" if len(labels) > 1 else ""
        blocks.append(title + table(head, cause_rows,
                                    f"Skoru değiştiren {num(cl[l]['causeTotal'])} sınamanın en sık 10 nedeni."))
    causes = pair(blocks)

    wit_rows = []
    for w in m["witnesses"]:
        cells = "".join(f"<td class='n'>{w['results'][l]['before']} → {w['results'][l]['after']} "
                        f"<b>({signed(w['results'][l]['delta'])})</b></td>" for l in labels)
        wit_rows.append(f"<tr><th>{esc(w['title'])}</th><td class='n'>{tl(w['before'])} → {tl(w['after'])}</td>{cells}</tr>")
    witnesses = table(["Sınama", f"Değişen girdi"] + [f"Skor ({esc(l)})" for l in labels], wit_rows,
                      "Elle kurulmuş profiller (girdileri out/iq_model_*.json'da); skorlar üründeki kurallardan.")
    return (f"<h3>En büyük |Δskor| dağılımı (±%1)</h3>{chart}<h3>Girdi başına</h3>{per_input}"
            f"<h3>Skoru en sık ne oynatıyor</h3>{causes}<h3>1 TL ile en büyük sıçramalar</h3>{witnesses}")


def heat_table(h: dict, labels: list[str]) -> str:
    xs, ys = h["xs"], h["ys"]
    cols = [i for i, _ in h["xTicks"]]
    rows_idx = [i for i, _ in h["yTicks"]]
    fmt_x = {i: t for i, t in h["xTicks"]}
    fmt_y = {i: t for i, t in h["yTicks"]}
    rows = []
    for j in reversed(rows_idx):
        cells = []
        for i in cols:
            k = j * len(xs) + i
            cells.append("<td class='n'>" + " / ".join(str(h["z"][l][k]) for l in labels) + "</td>")
        rows.append(f"<tr><th>{esc(fmt_y[j])}</th>{''.join(cells)}</tr>")
    head = [f"{esc(h['yLabel'])} \\ {esc(h['xLabel'])}"] + [esc(fmt_x[i]) for i in cols]
    note = "Hücrelerde skor" + (f" ({' / '.join(labels)})" if len(labels) > 1 else "") + "; seçilmiş satır ve sütunlar."
    return details("Tablo görünümü", table(head, rows, note))


def sobol_html(m: dict, labels: list[str]) -> str:
    sob = m["sobol"]
    first = labels[0]
    order = sorted(KEYS, key=lambda k: -next(r["ST"] for r in sob[first]["rows"] if r["input"] == k))
    top = max(max(r["SThi"], r["S1hi"]) for l in labels for r in sob[l]["rows"])
    scale = min(1.0, math.ceil(top * 10 + 0.5) / 10)
    rows = []
    for k in order:
        lines = []
        for i, l in enumerate(labels):
            r = next(x for x in sob[l]["rows"] if x["input"] == k)

            def pos(v):
                return max(0.0, min(1.0, v / scale)) * 100

            tip = (f"{esc(l)}: birinci derece {num(r['S1'], 3)} [{num(r['S1lo'], 2)}; {num(r['S1hi'], 2)}], "
                   f"toplam {num(r['ST'], 3)} [{num(r['STlo'], 2)}; {num(r['SThi'], 2)}]")
            lines.append(
                f'<div class="db" tabindex="0" data-tip="{tip}"><div class="dtrack">'
                f'<span class="ci up" style="left:{pos(r["S1lo"]):.2f}%;width:{max(pos(r["S1hi"]) - pos(r["S1lo"]), 0.3):.2f}%"></span>'
                f'<span class="ci down" style="left:{pos(r["STlo"]):.2f}%;width:{max(pos(r["SThi"]) - pos(r["STlo"]), 0.3):.2f}%"></span>'
                f'<span class="conn c{i}" style="left:{pos(min(r["S1"], r["ST"])):.2f}%;width:{abs(pos(r["ST"]) - pos(r["S1"])):.2f}%"></span>'
                f'<span class="mk dot sw{i}" style="left:{pos(r["S1"]):.2f}%"></span>'
                f'<span class="mk sq sw{i}" style="left:{pos(r["ST"]):.2f}%"></span></div>'
                f'<div class="dbv">{idx(r["S1"])} · <b>{idx(r["ST"])}</b></div></div>')
        rows.append(f'<div class="drow"><div class="hl">{esc(SOBOL_SHORT[k])}</div><div>{"".join(lines)}</div></div>')
    ticks = "".join(f'<span style="left:{t / scale * 100:.1f}%">{num(t, 1)}</span>'
                    for t in [x / 10 for x in range(0, int(scale * 10) + 1, 2 if scale > 0.6 else 1)])
    keys = ('<div class="legend"><span class="key"><span class="mkk dot"></span><span>birinci derece S<sub>i</sub></span></span>'
            '<span class="key"><span class="mkk sq"></span><span>toplam S<sub>Ti</sub></span></span>'
            '<span class="key"><span class="cik"></span><span>%95 bootstrap aralığı (üst: S<sub>i</sub>, alt: S<sub>Ti</sub>)</span></span>'
            + "".join(f'<span class="key"><span class="sw sw{i}"></span>{esc(l)}</span>' for i, l in enumerate(labels) if len(labels) > 1)
            + "</div>")
    chart = (keys + f'<div class="dchart" role="img" aria-label="Sobol indeksleri">'
             f'<div class="drow"><div class="hl"></div><div class="db head"><div></div><div class="dbv">S<sub>i</sub> · '
             f'<b>S<sub>Ti</sub></b></div></div></div>{"".join(rows)}'
             f'<div class="drow"><div class="hl"></div><div class="db axisrow"><div class="dticks">{ticks}</div><div></div></div></div></div>')
    tv = []
    for k in order:
        cells = "".join(
            f"<td class='n'>{num(r['S1'], 3)} <span class='hint'>[{num(r['S1lo'], 2)}; {num(r['S1hi'], 2)}]</span></td>"
            f"<td class='n'>{num(r['ST'], 3)} <span class='hint'>[{num(r['STlo'], 2)}; {num(r['SThi'], 2)}]</span></td>"
            for l in labels for r in [next(x for x in sob[l]["rows"] if x["input"] == k)])
        tv.append(f"<tr><th>{esc(SOBOL_TR[k])}</th>{cells}</tr>")
    head = ["Girdi"]
    for l in labels:
        sfx = f" ({esc(l)})" if len(labels) > 1 else ""
        head += [f"S<sub>i</sub>{sfx}", f"S<sub>Ti</sub>{sfx}"]
    sums = " · ".join(f"{esc(l)}: ΣS<sub>i</sub> = {num(sob[l]['sumS1'], 2)}, skor ortalaması {num(sob[l]['mean'], 1)}, "
                      f"varyans {num(sob[l]['variance'], 0)}" for l in labels)
    chart += details("Tablo görünümü", table(head, tv, sums))

    dist_rows = [f"<tr><th>{esc(INPUT_TR[k])}</th><td>{esc(name)}</td><td>{esc(desc)}</td></tr>"
                 for k, (name, desc, _fn) in zip(KEYS, DISTRIBUTIONS)]
    dist = table(["Girdi", "Örneklenen değişken", "Dağılım"], dist_rows,
                 "Değişkenler bağımsız; tutarlar gelirle çarpılarak TL'ye çevrildi (gelir = gelir düzeyi). Bu yüzden "
                 "“gelir” indeksi, oranlar sabitken gelir düzeyinin etkisidir: yalnız mutlak tutarlı kurallardan gelir. "
                 "Taksit ayrı çekilmiyor: borçtan ve vadeden türetiliyor (annüite, en fazla gelirin %60'ı), bu yüzden "
                 "taksit satırının indeksi vadenin (geri ödeme yoğunluğunun) etkisidir, borç satırınınki taksitin "
                 "büyüklüğünü de içerir.")
    rule_rows = []
    for l in labels:
        total = sum(sob[l]["rules"].values())
        rule_rows.append(f"<tr><th>{esc(l)}</th>" + "".join(
            f"<td class='n'>{pct(sob[l]['rules'].get(r, 0) / total)}</td>" for r in ["None"] + m["rules"])
            + "".join(f"<td class='n'>{pct(sob[l]['segments'].get(s, 0) / total)}</td>" for s in ("LOW", "MEDIUM", "HIGH"))
            + "</tr>")
    rules = table(["Puanlayıcı", "Kural yok"] + [esc(RULE_TR.get(r, r)) for r in m["rules"]] + ["LOW", "MEDIUM", "HIGH"],
                  rule_rows, f"Nüfusun ({num(2 * m['sobolN'])} profil: A ve B) kural ve segment payları.")
    return chart + "<h3>Örnekleme dağılımları</h3>" + dist + rules


def cheapest_html(m: dict, labels: list[str]) -> str:
    parts = []
    for label in labels:
        ch = m["cheapest"][label]
        rows = []
        for pkey, plabel, *_r in PERSONAS:
            c = ch[pkey]
            cells = []
            if c["target"] > 100:
                rows.append(f"<tr><th>{esc(plabel)}</th><td class='n'>{c['base']}</td><td colspan='{len(KEYS)}' class='hint'>"
                            f"skor 90'ın üstünde: +10 puan mümkün değil</td></tr>")
                continue
            for k in KEYS:
                r = c["rows"][k]
                if r["status"] == "zero":
                    cells.append("<td class='hint'>zaten 0</td>")
                elif r["status"] == "lowest":
                    cells.append("<td class='hint'>zaten 1</td>")
                elif r["status"] == "none":
                    cells.append("<td class='hint'>ulaşılamıyor</td>")
                elif k == "impatienceLevel":
                    base = next(p for q, *_x, p in PERSONAS if q == pkey)[k]
                    cells.append(f"<td class='n'>{base} → {int(r['value'])}<div class='hint'>beyanla, skor {r['score']}</div></td>")
                else:
                    rel = f" ({'+' if r['delta'] > 0 else '−'}{pct(abs(r['rel']))})" if r["rel"] is not None else " (sıfırdan)"
                    hit = " class='n hit'" if c["best"] == k else " class='n'"
                    star = "★ " if c["best"] == k else ""
                    rule = f" · {r['rule']}" if r["rule"] else ""
                    kind = "aylık, kalıcı" if k in ("monthlyIncome", "monthlyExpenses", "monthlyDebtPayment") else "tek seferlik"
                    tip = (f"{signed(r['delta'])} TL ({kind})\n{INPUT_TR[k]}: {tl(r['value'] - r['delta'])} → {tl(r['value'])}"
                           f"\naylık gelirin {num(r['incomeMonths'], 2)} katı · skor {c['base']} → {r['score']}{rule}")
                    cells.append(f"<td{hit} data-tip=\"{esc(tip)}\">{star}{signed(r['delta'])} TL"
                                 f"<div class='hint'>{rel.strip(' ()')} · skor {r['score']}{'*' if rule else ''}</div></td>")
            rows.append(f"<tr><th>{esc(plabel)}</th><td class='n'>{c['base']} → {c['target']}</td>{''.join(cells)}</tr>")
        title = f"<h3>{esc(label)}</h3>" if len(labels) > 1 else ""
        parts.append(title + table(["Kişi", "Skor → hedef"] + [esc(SHORT_TR[k]) for k in KEYS], rows,
                                   "Tek girdi, olumlu yönde (gelir/nakit/yatırım artar; gider/taksit/borç azalır), diğerleri "
                                   "sabit. Hücre: hedefe ulaştıran en küçük değişiklik (TL), altında girdinin yüzde kaçı "
                                   "olduğu ve varılan skor; üzerine gelince aylık gelire oranı. ★ = yüzde olarak en küçük "
                                   "parasal değişiklik. Gelir, gider ve taksit aylık (kalıcı) değişikliktir; borç, nakit ve "
                                   "yatırım tek seferlik. Sabırsızlık sütunu yalnız beyanın değişmesi. * = varılan skorda bir kural "
                                   "ya da etiket var (üzerine gelince görünür).", "cheap"))
    return "".join(parts)


def weaknesses_v2(m: dict, first: str) -> str:
    sob = {r["input"]: r for r in m["sobol"][first]["rows"]}
    dep = m["deps"][first]["matrix"]
    cl = m["cliffs"][first]
    wit = m["witnesses"]
    inside = max(abs(w["results"][first]["delta"]) for w in wit if not w["ruleDriven"])
    return f"""
<ul class="points">
<li><b>Basamaklı fonksiyonlar uçurum üretir.</b> Eşiklerin tam üstünde 1 TL skoru {inside} puana kadar (eşikler çakışınca),
kural eşiklerinde 100 puana kadar oynatabiliyor. Örnek nüfusta ±%1'lik tek bir değişiklik profillerin {pct(cl['atLeast'][5])}'inde
skoru 5 puan ya da daha fazla değiştiriyor.</li>
<li><b>Gider üç kez sayılıyor.</b> Gider rezerv ayının paydasında, tasarruf oranında ve gider oranında var
({num(dep['monthlyExpenses']['__reach'])} puanlık faktöre dokunuyor). s = 1 − e − p olduğundan tasarruf ve gider oranı neredeyse
aynı bilgiyi iki kez puanlıyor; YÖK araştırması da bu çift sayımı not etmişti.</li>
<li><b>Nakit ve yatırım iki kez sayılıyor.</b> Hem rezervde (yatırımın yarısı) hem net borçta (tamamı): aynı lira iki faktörü
birden taşıyabiliyor.</li>
<li><b>Gelir düzeyi kendi başına yalnız kurallarla etkili.</b> Tüm tutarlar gelirle orantılı büyüyünce skor değişmiyor;
gelir düzeyinin birinci derece indeksi {num(sob['monthlyIncome']['S1'], 2)}, toplam indeksi {num(sob['monthlyIncome']['ST'], 2)}.
Kural eşikleri TL cinsinden sabit: enflasyonla anlamları kayar.</li>
<li><b>Sabırsızlık serbest bir öz-beyan.</b> {m['params']['impatience'][first][0]} puan, doğrulanmıyor; tek seviye düşürmek
2–3 puan getiriyor. Toplam Sobol indeksi {idx(sob['impatienceLevel']['ST'])}.</li>
<li><b>Eşiklerin çoğunun dayanağı zayıf.</b> 1 ay rezerv, gider %40/%60, net borç 0,5/1/3 yıl ve tasarruf ≥ 0 eşikleri için
kaynak bulunamadı; ağırlıklar uzman görüşü; HIGH segmenti (71) FinHealth'in sağlıklı eşiğinden (80) cömert.</li>
</ul>"""


def weaknesses_v3(m: dict, label: str, base: str | None) -> str:
    sob = {r["input"]: r for r in m["sobol"][label]["rows"]}
    dep = m["deps"][label]["matrix"]
    cl = m["cliffs"][label]

    def was(text: str) -> str:
        return f" (v2: {text})" if base else ""

    b_sob = {r["input"]: r for r in m["sobol"][base]["rows"]} if base else {}
    segs = m["sobol"][label]["segments"]
    total = sum(segs.values())
    b_segs = m["sobol"][base]["segments"] if base else {}
    b_total = sum(b_segs.values()) or 1
    return f"""
<ul class="points">
<li><b>Uçurumlar kapandı.</b> 1–2 TL'lik sınama çiftlerinde en büyük sıçrama {max(one_tl_deltas(m, label))} puan
{was(str(max(one_tl_deltas(m, base))) if base else '')}; ±%1'lik tek girdi değişikliğinde en büyük sıçrama {cl['max']}
{was(str(m['cliffs'][base]['max']) if base else '')}, skoru ≥ 5 puan oynayan profil {pct(cl['atLeast'][5])}
{was(pct(m['cliffs'][base]['atLeast'][5]) if base else '')}.</li>
<li><b>Gider oranı faktörü kalktı.</b> Gider artık rezervin paydasında (gider + taksit), tasarrufta, fon hedefinde ve
servet pistinde; ulaştığı puan {num(dep['monthlyExpenses']['__reach'])}. Bağımlılık matrisinde neredeyse her girdi dört
parasal faktöre birden dokunuyor, ama her biri küçük ve sürekli bir etkiyle.</li>
<li><b>Aynı lira bir kez sayılıyor.</b> Likit varlık önce 6 aylık fon hedefini dolduruyor; yalnız hedefin üstü borçtan
düşülüyor (parametre tablosundaki sınama).</li>
<li><b>TL eşiği yok.</b> Gelir düzeyinin toplam Sobol indeksi {num(sob['monthlyIncome']['ST'], 2)}
{was(num(b_sob['monthlyIncome']['ST'], 2) if base else '')}: oranlar sabitken gelir düzeyi skoru artık değiştirmiyor. Bunun
bedeli ölçekten bağımsızlık: 1 TL ile 100.000 TL gelir aynı oranlarla aynı skoru alır (öneri, bölüm 9).</li>
<li><b>Sabırsızlık 5 puan.</b> Beyanı 5'ten 1'e çekmek {m['params']['impatience'][label][0] - m['params']['impatience'][label][-1]}
puan getiriyor{was(str(m['params']['impatience'][base][0] - m['params']['impatience'][base][-1]) + ' puan' if base else '')};
toplam Sobol indeksi {idx(sob['impatienceLevel']['ST'])}.</li>
<li><b>Borç ve vade.</b> Borcun toplam Sobol indeksi {idx(sob['totalDebt']['ST'])}{was(idx(b_sob['totalDebt']['ST']) if base else '')},
vadenin {idx(sob['monthlyDebtPayment']['ST'])}{was(idx(b_sob['monthlyDebtPayment']['ST']) if base else '')}. Taksit borçtan ve
vadeden türetildiği için borç indeksi taksitin büyüklüğünü de içeriyor. Faiz tabanı profillerin
{pct(m['sobol'][label]['warnings'].get('Installment below interest', 0) / total)}'inde bağlıyor: uzun vadeli, düşük faizli
kredilerde ve gelirin %60'ıyla ödenemeyecek kadar büyük borçlarda (öneri belgesinin kalibre nüfusunda %17,1).</li>
<li><b>Segment payları bu örnek nüfusta:</b> LOW {pct(segs.get('LOW', 0) / total)}, MEDIUM {pct(segs.get('MEDIUM', 0) / total)},
HIGH {pct(segs.get('HIGH', 0) / total)}{was(f"{pct(b_segs.get('LOW', 0) / b_total)} / {pct(b_segs.get('MEDIUM', 0) / b_total)} / {pct(b_segs.get('HIGH', 0) / b_total)}") if base else ''}.
Sınırlar 41 / 71 olarak kaldı; HIGH'ın FinHealth gibi 80'den başlaması açık bir karar.</li>
<li><b>Kalanlar.</b> Kendi beyanı hâlâ puan getiriyor (gideri eksik bildirmek, sabırsızlık). Net borç çapaları (0,5/1/3/5 yıl),
tavan (5/15 yıl), faiz tabanı (%3,5) ve gider tabanı (%10) gerekçeli yargı; pist (25 yıl) ABD verisinden. Ağırlıklar uzman
görüşü.</li>
</ul>"""


def weaknesses_html(m: dict, labels: list[str]) -> str:
    v2 = labels_with(m, labels, V2_KEYS)
    v3 = labels_with(m, labels, V3_KEYS)
    parts = []
    if v2:
        parts.append(("<h3>v2'nin bilinen zayıflıkları</h3>" if v3 else "") + weaknesses_v2(m, v2[0]))
    if v3:
        parts.append("<h3>v3: ne değişti, ne kaldı</h3>" + weaknesses_v3(m, v3[0], v2[0] if v2 else None))
    if not parts:
        parts.append(weaknesses_v2(m, labels[0]) if m["factorKeys"][labels[0]] == V2_KEYS else "")
    parts.append("""
<ul class="points">
<li><b>Sobol sonuçları seçilen dağılıma bağlı.</b> Değişkenler bağımsız ve sentetik örneklendi (taksit borçtan ve vadeden
türetildi); gerçek nüfusta gider, gelir ve borç ilişkili. Sonuçlar “bu kurallar hangi girdiye ne kadar tepki veriyor” sorusunu yanıtlar, Türkiye nüfusunu temsil etmez
(bkz. report.html ve v3 önerisindeki kalibre nüfus).</li>
</ul>""")
    return "".join(parts)


# --- page -------------------------------------------------------------------------------------------------------------
STYLE = """
:root { color-scheme:light; --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781;
  --line:#e1e0d9; --axis:#c3c2b7; --accent:#2a78d6; --track:#ecebe6; --code:#f2f1ed;
  --ser0:#2a78d6; --ser1:#eb6834; --ser2:#1baf7a;
  --good:#0ca30c; --warn:#fab219; --crit:#d03b3b;
  --q0:#cde2fb; --q1:#b7d3f6; --q2:#9ec5f4; --q3:#86b6ef; --q4:#6da7ec; --q5:#5598e7; --q6:#3987e5; --q7:#2a78d6;
  --q8:#256abf; --q9:#1c5cab; --q10:#184f95; --q11:#104281; --q12:#0d366b;
  --m1:#86b6ef; --m1t:#0b0b0b; --m2:#3987e5; --m2t:#0b0b0b; --m3:#1c5cab; --m3t:#ffffff; --m4:#0d366b; --m4t:#ffffff;
  --mid:#f0efec; --neg:#e34948; --pos:#2a78d6; --shadow:0 4px 18px rgba(11,11,11,.12); }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { color-scheme:dark; --page:#0d0d0d; --surface:#1a1a19;
  --ink:#f0efec; --ink-2:#c3c2b7; --line:#2c2c2a; --axis:#383835; --accent:#3987e5; --track:#2c2c2a; --code:#262624;
  --ser0:#3987e5; --ser1:#d95926; --ser2:#199e70;
  --q0:#0d366b; --q1:#104281; --q2:#184f95; --q3:#1c5cab; --q4:#256abf; --q5:#2a78d6; --q6:#3987e5; --q7:#5598e7;
  --q8:#6da7ec; --q9:#86b6ef; --q10:#9ec5f4; --q11:#b7d3f6; --q12:#cde2fb;
  --m1:#184f95; --m1t:#f0efec; --m2:#256abf; --m2t:#f0efec; --m3:#5598e7; --m3t:#0b0b0b; --m4:#9ec5f4; --m4t:#0b0b0b;
  --mid:#383835; --neg:#e66767; --pos:#3987e5; --shadow:0 4px 18px rgba(0,0,0,.5); } }
:root[data-theme="dark"] { color-scheme:dark; --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink-2:#c3c2b7;
  --line:#2c2c2a; --axis:#383835; --accent:#3987e5; --track:#2c2c2a; --code:#262624;
  --ser0:#3987e5; --ser1:#d95926; --ser2:#199e70;
  --q0:#0d366b; --q1:#104281; --q2:#184f95; --q3:#1c5cab; --q4:#256abf; --q5:#2a78d6; --q6:#3987e5; --q7:#5598e7;
  --q8:#6da7ec; --q9:#86b6ef; --q10:#9ec5f4; --q11:#b7d3f6; --q12:#cde2fb;
  --m1:#184f95; --m1t:#f0efec; --m2:#256abf; --m2t:#f0efec; --m3:#5598e7; --m3t:#0b0b0b; --m4:#9ec5f4; --m4t:#0b0b0b;
  --mid:#383835; --neg:#e66767; --pos:#3987e5; --shadow:0 4px 18px rgba(0,0,0,.5); }
* { box-sizing:border-box; }
[hidden] { display:none !important; }
body { margin:0; background:var(--page); color:var(--ink); font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1180px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:26px; margin:0 0 4px; line-height:1.25; }
h2 { font-size:20px; margin:36px 0 8px; padding-top:12px; border-top:1px solid var(--line); }
h3 { font-size:16px; margin:20px 0 6px; }
p { max-width:80ch; }
.hint { color:var(--muted); font-size:13px; }
code { background:var(--code); padding:1px 5px; border-radius:4px; font-size:13px; overflow-wrap:anywhere; }
a { color:var(--accent); }
.top { display:flex; justify-content:space-between; align-items:flex-start; gap:12px; flex-wrap:wrap; }
.theme { font:inherit; font-size:13px; color:var(--ink-2); background:var(--surface); border:1px solid var(--line);
  border-radius:8px; padding:4px 10px; cursor:pointer; }
nav { display:flex; flex-wrap:wrap; gap:6px 14px; font-size:14px; margin:14px 0; }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin:18px 0; }
.tile { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:12px 14px; font-size:14px; }
.tile .big { font-size:28px; font-weight:700; line-height:1.2; }
.formula { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:4px 16px; font-size:14px; }
.formula var { font-style:italic; font-family:Cambria,"Times New Roman",serif; font-size:15px; }
.scroll { overflow-x:auto; margin:8px 0; }
table { border-collapse:collapse; width:100%; font-size:13.5px; background:var(--surface); }
caption { caption-side:bottom; text-align:left; color:var(--muted); font-size:12.5px; padding-top:6px; }
th, td { padding:6px 8px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
thead th { font-size:12px; color:var(--ink-2); font-weight:600; vertical-align:bottom; }
tbody th { font-weight:500; }
td.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
td.hit { box-shadow:inset 0 0 0 2px var(--accent); font-weight:600; }
td.wide { min-width:200px; } td.chk { min-width:150px; font-size:13px; }
table.matrix td.mx { text-align:center; }
.m0 { color:var(--muted); } .m1 { background:var(--m1); color:var(--m1t); } .m2 { background:var(--m2); color:var(--m2t); }
.m3 { background:var(--m3); color:var(--m3t); } .m4 { background:var(--m4); color:var(--m4t); }
table.matrix td.mx { border:2px solid var(--surface); }
.v { display:inline-block; min-width:44px; }
.track { display:inline-block; width:60px; height:6px; background:var(--track); border-radius:3px; margin-left:6px; vertical-align:middle; overflow:hidden; }
.fill { display:block; height:100%; background:var(--accent); border-radius:3px; }
.lvl { display:inline-flex; gap:5px; align-items:center; white-space:nowrap; }
.ico { font-weight:700; } .ico.good { color:var(--good); } .ico.warn { color:var(--warn); } .ico.crit { color:var(--crit); }
.ico.none { color:var(--muted); }
details.tv { margin:6px 0 14px; } details.tv summary { cursor:pointer; color:var(--ink-2); font-size:13.5px; }
.legend { display:flex; flex-wrap:wrap; gap:4px 16px; font-size:13px; color:var(--ink-2); margin:10px 0 4px; }
.key { display:inline-flex; align-items:center; gap:6px; }
.sw { display:inline-block; width:12px; height:12px; border-radius:3px; }
.sw0 { background:var(--ser0); } .sw1 { background:var(--ser1); } .sw2 { background:var(--ser2); }
.lk { display:inline-block; width:14px; height:2px; vertical-align:middle; margin-right:6px; border-radius:1px; }
.controls { display:flex; flex-wrap:wrap; gap:8px 14px; align-items:center; margin:10px 0; font-size:14px; }
.controls label { display:inline-flex; gap:6px; align-items:center; color:var(--ink-2); }
select, .seg button { font:inherit; font-size:14px; color:var(--ink); background:var(--surface); border:1px solid var(--line);
  border-radius:8px; padding:4px 8px; max-width:100%; }
.seg { display:inline-flex; gap:0; } .seg button { border-radius:0; cursor:pointer; margin-left:-1px; }
.seg button:first-child { border-radius:8px 0 0 8px; margin-left:0; } .seg button:last-child { border-radius:0 8px 8px 0; }
.seg button[aria-pressed="true"] { background:var(--track); font-weight:600; }
.card { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:10px 12px; margin:8px 0; }
.chart { width:100%; position:relative; } .chart svg { display:block; width:100%; overflow:visible; touch-action:pan-y; }
.chart svg:focus { outline:2px solid var(--accent); outline-offset:2px; }
.grid line { stroke:var(--line); stroke-width:1; } .axisline { stroke:var(--axis); stroke-width:1; }
.tick text, .axlabel { fill:var(--muted); font-size:11.5px; font-variant-numeric:tabular-nums; }
.band { fill:var(--muted); font-size:11px; }
.ln { fill:none; stroke-width:2; stroke-linejoin:round; stroke-linecap:round; }
.ln.s0 { stroke:var(--ser0); } .ln.s1 { stroke:var(--ser1); } .ln.s2 { stroke:var(--ser2); }
.pt { stroke:var(--surface); stroke-width:2; } .pt.s0 { fill:var(--ser0); } .pt.s1 { fill:var(--ser1); } .pt.s2 { fill:var(--ser2); }
.cross { stroke:var(--ink-2); stroke-width:1; } .basel { stroke:var(--muted); stroke-width:1; }
.stepmark { fill:var(--muted); } .steplabel { fill:var(--ink-2); font-size:11.5px; font-weight:600;
  paint-order:stroke; stroke:var(--surface); stroke-width:3px; stroke-linejoin:round; }
.halo { paint-order:stroke; stroke:var(--surface); stroke-width:3px; stroke-linejoin:round; }
#tip { position:fixed; z-index:10; pointer-events:none; background:var(--surface); color:var(--ink); border:1px solid var(--line);
  border-radius:8px; box-shadow:var(--shadow); padding:8px 10px; font-size:12.5px; line-height:1.45; max-width:340px; display:none; }
#tip .tv1 { font-weight:700; font-size:14px; } #tip .tl { color:var(--ink-2); } #tip .tm { color:var(--muted); font-size:12px; }
#tip .row { display:flex; align-items:baseline; gap:6px; }
.flowbox { overflow-x:auto; } .flow-svg { width:100%; display:block; }
.pair { display:grid; grid-template-columns:repeat(auto-fit, minmax(min(100%, 520px), 1fr)); gap:4px 20px; align-items:start; }
.pair > div { min-width:0; }
.flow-svg .edge { fill:none; stroke:var(--axis); stroke-width:1.2; }
.flow-svg .node rect { fill:var(--surface); stroke:var(--axis); stroke-width:1; }
.flow-svg .node.in rect { stroke:var(--ink-2); } .flow-svg .node.rule rect, .flow-svg .node.out rect { fill:var(--track); }
.flow-svg .node { cursor:pointer; outline:none; } .flow-svg .t { font-size:12.5px; font-weight:600; fill:var(--ink); }
.flow-svg .f { font-size:11.5px; fill:var(--ink-2); } .flow-svg .col { font-size:11px; fill:var(--muted); dominant-baseline:hanging; }
.flow-svg.dim .node { opacity:.28; } .flow-svg.dim .node.on { opacity:1; } .flow-svg.dim .edge { opacity:.18; }
.flow-svg.dim .edge.on { opacity:1; stroke:var(--accent); stroke-width:2; }
.flow-svg .node.on rect { stroke:var(--accent); stroke-width:2; } .flow-svg .node:focus-visible rect { stroke-width:3; }
.hchart { margin:8px 0; } .hrow, .drow { display:grid; grid-template-columns:92px 1fr; gap:8px; align-items:center; }
.hl { font-size:13px; color:var(--ink-2); text-align:right; font-variant-numeric:tabular-nums; }
.hbars { display:flex; flex-direction:column; gap:2px; padding:3px 0; }
.hb { display:flex; align-items:center; gap:6px; min-height:12px; outline:none; }
.hb:focus-visible { outline:2px solid var(--accent); }
.hbar { display:block; height:10px; border-radius:0 4px 4px 0; min-width:1px; }
.hv { font-size:12px; color:var(--ink-2); font-variant-numeric:tabular-nums; white-space:nowrap; }
.dchart { margin:8px 0; max-width:900px; }
.db { display:grid; grid-template-columns:1fr 92px; gap:8px; align-items:center; outline:none; }
.db:focus-visible { outline:2px solid var(--accent); }
.dtrack { position:relative; height:26px; border-left:1px solid var(--axis); }
.db .ci { position:absolute; height:1.5px; background:var(--muted); opacity:.7; border-radius:1px; }
.db .ci.up { top:5px; } .db .ci.down { top:20px; }
.db .conn { position:absolute; top:11px; height:4px; border-radius:2px; opacity:.45; }
.conn.c0 { background:var(--ser0); } .conn.c1 { background:var(--ser1); } .conn.c2 { background:var(--ser2); }
.db .mk { position:absolute; top:6px; width:14px; height:14px; margin-left:-7px; box-shadow:0 0 0 2px var(--surface); }
.db .dot { border-radius:50%; } .db .sq { border-radius:3px; width:12px; height:12px; margin-left:-6px; top:7px; }
.dbv { font-size:12.5px; color:var(--ink-2); font-variant-numeric:tabular-nums; white-space:nowrap; }
.db.head .dbv { color:var(--muted); font-size:12px; } .db.axisrow { align-items:start; }
.dticks { position:relative; height:18px; border-top:1px solid var(--axis); }
.dticks span { position:absolute; transform:translateX(-50%); font-size:11.5px; color:var(--muted); top:2px; }
.mkk { display:inline-block; width:12px; height:12px; background:var(--ink-2); } .mkk.dot { border-radius:50%; }
.mkk.sq { border-radius:3px; width:11px; height:11px; } .cik { display:inline-block; width:16px; height:2px; background:var(--muted); }
.scale { display:flex; align-items:center; gap:8px; font-size:12px; color:var(--muted); margin:6px 0; flex-wrap:wrap; }
.ramp { display:flex; height:10px; width:220px; border-radius:3px; overflow:hidden; }
.ramp span { flex:1; }
.heat .cell { shape-rendering:crispEdges; }
.q0{fill:var(--q0)}.q1{fill:var(--q1)}.q2{fill:var(--q2)}.q3{fill:var(--q3)}.q4{fill:var(--q4)}.q5{fill:var(--q5)}.q6{fill:var(--q6)}
.q7{fill:var(--q7)}.q8{fill:var(--q8)}.q9{fill:var(--q9)}.q10{fill:var(--q10)}.q11{fill:var(--q11)}.q12{fill:var(--q12)}
.ruleline { fill:none; stroke:var(--ink); stroke-width:1.5; } .rulelabel { fill:var(--ink); font-size:12px; font-weight:600;
  paint-order:stroke; stroke:var(--surface); stroke-width:3.5px; stroke-linejoin:round; }
.hover { fill:none; stroke:var(--ink); stroke-width:1.5; pointer-events:none; }
.cellval { fill:var(--ink); font-size:11px; font-weight:600; pointer-events:none; font-variant-numeric:tabular-nums;
  paint-order:stroke; stroke:var(--surface); stroke-width:3px; stroke-linejoin:round; }
.points li { margin:6px 0; max-width:95ch; }
table.params td, table.params th { font-size:13px; }
@media (max-width:600px) { .hrow, .drow { grid-template-columns:70px 1fr; } h1 { font-size:22px; } .tile .big { font-size:24px; } }
@media (forced-colors: active) { .sw, .hbar, .mk, .mkk { forced-color-adjust:none; } }
"""

SCRIPT = r"""
(() => {
const D = JSON.parse(document.getElementById('iq-data').textContent);
const NS = 'http://www.w3.org/2000/svg';
const $ = (s, r = document) => r.querySelector(s);
function S(tag, attrs, parent, text) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (text != null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
function H(tag, cls, parent, text) {
  const e = document.createElement(tag);
  if (cls) e.className = cls;
  if (text != null) e.textContent = text;
  if (parent) parent.appendChild(e);
  return e;
}
const nf = (v, d = 0) => Number(v).toLocaleString('tr-TR', {minimumFractionDigits: d, maximumFractionDigits: d});
function compact(v) {
  const a = Math.abs(v);
  if (a >= 1e6) return nf(v / 1e6, a >= 1e7 || a % 1e6 === 0 ? 0 : 1) + ' Mn';
  if (a >= 1e3) return nf(v / 1e3, a >= 1e4 || a % 1e3 === 0 ? 0 : 1) + ' bin';
  return nf(v);
}
const tl = v => nf(v, Math.abs(v - Math.round(v)) < 0.005 ? 0 : 2) + ' TL';
const pc = (v, d = 0) => '%' + nf(v * 100, d);
const debounce = (fn, ms) => { let t; return () => { clearTimeout(t); t = setTimeout(fn, ms); }; };
const labels = D.scorers.map(s => s.label);
const ruleName = i => i < 0 ? null : (D.ruleNames[D.rules[i]] || D.rules[i]);

// theme: system -> light -> dark
(() => {
  const btn = $('#theme'); if (!btn) return;
  const names = {'': 'Tema: sistem', light: 'Tema: açık', dark: 'Tema: koyu'};
  let cur = document.documentElement.getAttribute('data-theme') || '';
  try { cur = localStorage.getItem('iq-model-theme') || cur; } catch (e) {}
  const apply = () => { if (cur) document.documentElement.setAttribute('data-theme', cur); else document.documentElement.removeAttribute('data-theme'); btn.textContent = names[cur] || names['']; };
  apply();
  btn.addEventListener('click', () => { cur = cur === '' ? 'light' : cur === 'light' ? 'dark' : ''; try { localStorage.setItem('iq-model-theme', cur); } catch (e) {} apply(); });
})();

// tooltip: rows = [{value, label, key (series index), muted}]
const tip = $('#tip');
function showTip(rows, x, y) {
  tip.replaceChildren();
  rows.forEach((r, i) => {
    const row = H('div', 'row', tip);
    if (r.key != null) { const k = H('span', 'lk', row); k.style.background = `var(--ser${r.key})`; }
    if (r.value != null) H('span', i === 0 || r.key != null ? 'tv1' : 'tl', row, r.value);
    if (r.label) H('span', r.muted ? 'tm' : 'tl', row, r.label);
  });
  tip.style.display = 'block';
  const w = tip.offsetWidth, h = tip.offsetHeight, vw = window.innerWidth, vh = window.innerHeight;
  let left = x + 14, top = y + 14;
  if (left + w > vw - 8) left = Math.max(8, x - w - 14);
  if (top + h > vh - 8) top = Math.max(8, y - h - 14);
  tip.style.left = left + 'px'; tip.style.top = top + 'px';
}
const hideTip = () => { tip.style.display = 'none'; };
function tipFromText(text) {
  const lines = text.split('\n');
  return lines.map((l, i) => i === 0 ? {value: l} : {label: l, muted: i > 1});
}
document.addEventListener('pointerover', e => {
  const t = e.target.closest && e.target.closest('[data-tip]');
  if (t) showTip(tipFromText(t.dataset.tip), e.clientX, e.clientY);
});
document.addEventListener('pointermove', e => {
  const t = e.target.closest && e.target.closest('[data-tip]');
  if (t) showTip(tipFromText(t.dataset.tip), e.clientX, e.clientY);
});
document.addEventListener('pointerout', e => { if (e.target.closest && e.target.closest('[data-tip]')) hideTip(); });
document.addEventListener('focusin', e => {
  const t = e.target.closest && e.target.closest('[data-tip]');
  if (t) { const b = t.getBoundingClientRect(); showTip(tipFromText(t.dataset.tip), b.left, b.bottom); }
});
document.addEventListener('focusout', e => { if (e.target.closest && e.target.closest('[data-tip]')) hideTip(); });

// flow diagram: hover or focus a node -> highlight what it touches
document.querySelectorAll('.flow-svg').forEach(svg => {
  const nodes = [...svg.querySelectorAll('.node')];
  const on = n => {
    svg.classList.add('dim');
    const ids = new Set(n.dataset.on.split(' ')), edges = new Set(n.dataset.edges.split(' '));
    nodes.forEach(m => m.classList.toggle('on', ids.has(m.dataset.id)));
    svg.querySelectorAll('.edge').forEach(p => p.classList.toggle('on', edges.has(p.id)));
  };
  const off = () => { svg.classList.remove('dim'); svg.querySelectorAll('.on').forEach(x => x.classList.remove('on')); };
  nodes.forEach(n => { n.addEventListener('pointerenter', () => on(n)); n.addEventListener('focus', () => on(n));
    n.addEventListener('pointerleave', off); n.addEventListener('blur', off); });
});

function niceTicks(lo, hi, count) {
  const span = hi - lo; if (span <= 0) return [lo];
  const raw = span / Math.max(1, count), mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(m => m * mag).find(s => s >= raw) || 10 * mag;
  const out = []; for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) out.push(Math.round(v * 1e6) / 1e6);
  return out;
}

// --- one-at-a-time sweeps ---
(() => {
  const selP = $('#sw-persona'), selI = $('#sw-input'), box = $('#sw-chart'), info = $('#sw-info'), tv = $('#sw-table');
  if (!selP) return;
  D.personas.forEach((p, i) => selP.add(new Option(p.label, i)));
  D.inputs.forEach((inp, i) => selI.add(new Option(inp.name, i)));
  selI.value = 1;
  const factorsText = (label, f) => D.factors[label].map((k, i) => `${D.factorShort[k] || k} ${f[i] == null ? '–' : f[i]}`).join(' · ');
  const runAt = (runs, v) => { let r = runs[0]; for (const x of runs) { if (x[0] <= v + 1e-9) r = x; else break; } return r; };
  const fmtX = (inp, v) => inp.money ? tl(v) : 'seviye ' + v;
  function draw() {
    const p = D.personas[selP.value], inp = D.inputs[selI.value], sw = D.sweeps[p.key][inp.key];
    info.replaceChildren();
    H('span', '', info, D.inputs.slice(0, 6).map(i => `${i.short} ${compact(p.profile[i.key])}`).join(' · ') + ` · sabırsızlık ${p.profile.impatienceLevel}`);
    labels.forEach((l, i) => { const r = p.results[l]; const s = H('span', 'key', info); s.style.marginLeft = '12px';
      if (labels.length > 1) { const k = H('span', 'lk', s); k.style.background = `var(--ser${i})`; }
      H('b', '', s, `${labels.length > 1 ? l + ': ' : 'skor '}${r.score} (${r.segment})`); if (r.rule) H('span', 'hint', s, ' ' + (D.ruleNames[r.rule] || r.rule)); });
    box.replaceChildren();
    const W = Math.max(300, box.clientWidth), Ht = 320, m = {l: 38, r: 14, t: 18, b: 40};
    const pw = W - m.l - m.r, ph = Ht - m.t - m.b;
    const lo = sw.lo, hi = sw.hi === sw.lo ? sw.lo + 1 : sw.hi;
    const X = v => m.l + (v - lo) / (hi - lo) * pw, Y = s => m.t + (100 - s) / 100 * ph;
    const inv = px => lo + (px - m.l) / pw * (hi - lo);
    const svg = S('svg', {viewBox: `0 0 ${W} ${Ht}`, height: Ht, tabindex: 0, role: 'img',
      'aria-label': `${p.label}: skor, ${inp.name} değişirken. Ok tuşlarıyla eşikler arasında gezilir.`}, box);
    const g = S('g', {class: 'grid'}, svg);
    [0, 20, 40, 60, 80, 100].forEach(s => { S('line', {x1: m.l, x2: m.l + pw, y1: Y(s), y2: Y(s)}, g);
      S('text', {x: m.l - 6, y: Y(s) + 4, 'text-anchor': 'end', class: 'axlabel'}, svg, s); });
    [[D.segmentMin.MEDIUM, 'MEDIUM'], [D.segmentMin.HIGH, 'HIGH']].forEach(([s, name]) => {
      S('text', {x: m.l + pw - 2, y: Y(s - 0.5) - 4, 'text-anchor': 'end', class: 'band halo'}, svg, `${name} ≥ ${s}`); });
    const ticks = sw.discrete ? [1, 2, 3, 4, 5] : niceTicks(lo, hi, Math.max(3, Math.floor(pw / 90)));
    S('line', {x1: m.l, x2: m.l + pw, y1: m.t + ph, y2: m.t + ph, class: 'axisline'}, svg);
    ticks.forEach(t => S('text', {x: X(t), y: m.t + ph + 16, 'text-anchor': 'middle', class: 'axlabel'}, svg, sw.discrete ? t : compact(t)));
    S('text', {x: m.l + pw, y: m.t + ph + 34, 'text-anchor': 'end', class: 'axlabel'}, svg, inp.name + (inp.money ? ' (TL)' : ''));
    // step lines and the cliffs between runs
    const steps = [];
    labels.forEach((l, si) => {
      const runs = sw.runs[l]; let d = `M${X(lo)},${Y(runs[0][2])}`;
      for (let k = 1; k < runs.length; k++) {
        d += ` H${X(runs[k][0])} V${Y(runs[k][2])}`;
        steps.push({series: si, x: runs[k][0], prev: runs[k - 1][1], from: runs[k - 1][2], to: runs[k][2], d: runs[k][2] - runs[k - 1][2]});
      }
      d += ` H${X(hi)}`;
      S('path', {d, class: `ln s${si}`}, svg);
    });
    const cliffs = steps.filter(st => Math.abs(st.d) >= 2);  // a linear scorer moves 1 point at a time: not a cliff
    cliffs.forEach(st => S('path', {d: `M${X(st.x) - 3.5},${m.t + ph + 6} h7 l-3.5,-6 z`, class: 'stepmark'}, svg));
    [...steps].filter(st => Math.abs(st.d) >= 5).sort((a, b) => Math.abs(b.d) - Math.abs(a.d)).slice(0, 4).forEach(st => {
      const yMid = Y((st.from + st.to) / 2);
      const right = X(st.x) < m.l + pw - 40;
      S('text', {x: X(st.x) + (right ? 5 : -5), y: yMid + 4, 'text-anchor': right ? 'start' : 'end', class: 'steplabel'}, svg,
        (st.d > 0 ? '+' : '−') + Math.abs(st.d));
    });
    // current value of the persona
    S('line', {x1: X(sw.base), x2: X(sw.base), y1: m.t, y2: m.t + ph, class: 'basel'}, svg);
    S('text', {x: X(sw.base), y: m.t - 5, 'text-anchor': X(sw.base) > m.l + pw - 30 ? 'end' : 'middle', class: 'axlabel'}, svg, 'mevcut');
    labels.forEach((l, si) => S('circle', {cx: X(sw.base), cy: Y(runAt(sw.runs[l], sw.base)[2]), r: 4.5, class: `pt s${si}`}, svg));
    // crosshair
    const cross = S('line', {y1: m.t, y2: m.t + ph, class: 'cross', visibility: 'hidden'}, svg);
    const dots = labels.map((l, si) => S('circle', {r: 4.5, class: `pt s${si}`, visibility: 'hidden'}, svg));
    const hit = S('rect', {x: m.l, y: m.t, width: pw, height: ph, fill: 'transparent'}, svg);
    function at(v, cx, cy) {
      if (sw.discrete) v = Math.min(5, Math.max(1, Math.round(v)));
      v = Math.min(hi, Math.max(lo, v));
      cross.setAttribute('x1', X(v)); cross.setAttribute('x2', X(v)); cross.setAttribute('visibility', 'visible');
      const rows = [{value: `${inp.name}: ${fmtX(inp, sw.discrete ? v : Math.round(v))}`}];
      labels.forEach((l, si) => {
        const r = runAt(sw.runs[l], v);
        dots[si].setAttribute('cx', X(v)); dots[si].setAttribute('cy', Y(r[2])); dots[si].setAttribute('visibility', 'visible');
        rows.push({key: si, value: String(r[2]), label: (labels.length > 1 ? l + ' · ' : '') + (ruleName(r[3]) || 'kural yok')});
        rows.push({label: factorsText(l, r[4]), muted: true});
      });
      const near = cliffs.filter(st => Math.abs(X(st.x) - X(v)) < 14);
      near.slice(0, 2).forEach(st => rows.push({label: `eşik ${fmtX(inp, st.x)}: ${st.from} → ${st.to}` + (labels.length > 1 ? ` (${labels[st.series]})` : ''), muted: true}));
      const b = svg.getBoundingClientRect();
      showTip(rows, cx != null ? cx : b.left + X(v) * b.width / W, cy != null ? cy : b.top + m.t);
    }
    const hide = () => { cross.setAttribute('visibility', 'hidden'); dots.forEach(d => d.setAttribute('visibility', 'hidden')); hideTip(); };
    hit.addEventListener('pointermove', e => { const b = svg.getBoundingClientRect(); at(inv((e.clientX - b.left) * W / b.width), e.clientX, e.clientY); });
    hit.addEventListener('pointerleave', hide);
    const even = sw.discrete ? [] : Array.from({length: 21}, (_, i) => lo + (hi - lo) * i / 20);
    const stops = [...new Set([lo, sw.base, hi, ...even, ...cliffs.flatMap(st => [st.prev, st.x])])].sort((a, b) => a - b);
    let cur = stops.indexOf(sw.base);
    svg.addEventListener('keydown', e => {
      if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') { cur = Math.min(stops.length - 1, Math.max(0, cur + (e.key === 'ArrowRight' ? 1 : -1))); at(stops[cur]); e.preventDefault(); }
      else if (e.key === 'Escape') hide();
    });
    svg.addEventListener('blur', hide);
    // table view
    tv.replaceChildren();
    labels.forEach(l => {
      if (labels.length > 1) H('h4', '', tv, l);
      const wrap = H('div', 'scroll', tv), t = H('table', '', wrap), hr = H('tr', '', H('thead', '', t));
      ['Aralık', 'Skor', 'Kural', 'Faktörler'].forEach(x => H('th', '', hr, x));
      const tb = H('tbody', '', t);
      sw.runs[l].forEach(r => { const tr = H('tr', '', tb);
        H('td', 'n', tr, r[0] === r[1] ? fmtX(inp, r[0]) : `${fmtX(inp, r[0])} – ${fmtX(inp, r[1])}`);
        H('td', 'n', tr, r[2]); H('td', '', tr, ruleName(r[3]) || '–'); H('td', '', tr, factorsText(l, r[4])); });
    });
  }
  selP.addEventListener('change', draw); selI.addEventListener('change', draw);
  window.addEventListener('resize', debounce(draw, 150));
  draw();
})();

// --- heatmaps ---
(() => {
  const host = $('#heat-switch');
  let view = labels[labels.length - 1];  // the newest rule set first; the switch shows the others
  const views = labels.length > 1 ? [...labels, 'fark'] : labels;
  if (host && labels.length > 1) {
    host.hidden = false;
    const seg = host.querySelector('.seg');
    views.forEach(v => { const b = H('button', '', seg, v === 'fark' ? `fark (${labels[1]} − ${labels[0]})` : v);
      b.type = 'button'; b.setAttribute('aria-pressed', v === view); b.addEventListener('click', () => { view = v;
      seg.querySelectorAll('button').forEach(x => x.setAttribute('aria-pressed', x === b)); drawAll(); }); });
  }
  const fmt = (kind, v) => kind === 'pct' ? pc(v) : kind === 'months' ? nf(v, 2) + ' ay' : tl(v);
  function draw(hd) {
    const box = document.getElementById(hd.id); if (!box) return;
    box.replaceChildren();
    const nx = hd.xs.length, ny = hd.ys.length;
    const W = Math.max(300, box.clientWidth), m = {l: 58, r: 10, t: 8, b: 42}, ph = 300, Ht = ph + m.t + m.b;
    const pw = W - m.l - m.r, cw = pw / nx, chh = ph / ny;
    const svg = S('svg', {viewBox: `0 0 ${W} ${Ht}`, height: Ht, class: 'heat', role: 'img', 'aria-label': `${hd.yLabel} × ${hd.xLabel}: skor ısı haritası`}, box);
    const diff = view === 'fark', base = diff ? labels[0] : view;
    const z = hd.z[base], z2 = diff ? hd.z[labels[1]] : null;
    const cellClass = k => {
      if (!diff) return 'cell q' + Math.round(z[k] * 12 / 100);
      return 'cell';
    };
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const k = j * nx + i;
      const r = S('rect', {x: m.l + i * cw, y: m.t + (ny - 1 - j) * chh, width: cw + 0.6, height: chh + 0.6, class: cellClass(k)}, svg);
      if (diff) { const d = z2[k] - z[k], a = Math.min(1, Math.abs(d) / 30);
        r.style.fill = d === 0 ? 'var(--mid)' : `color-mix(in oklab, ${d > 0 ? 'var(--pos)' : 'var(--neg)'} ${Math.round(25 + 75 * a)}%, var(--mid))`; }
    }
    // rule regions of the shown scorer: outline + label
    const rl = hd.rule[base];
    let path = '';
    for (let j = 0; j < ny; j++) for (let i = 0; i < nx; i++) {
      const k = j * nx + i, x0 = m.l + i * cw, y0 = m.t + (ny - 1 - j) * chh;
      if (i + 1 < nx && rl[k] !== rl[k + 1] && (rl[k] >= 0 || rl[k + 1] >= 0)) path += `M${x0 + cw},${y0} v${chh} `;
      if (j + 1 < ny && rl[k] !== rl[k + nx] && (rl[k] >= 0 || rl[k + nx] >= 0)) path += `M${x0},${y0} h${cw} `;
    }
    if (path) S('path', {d: path, class: 'ruleline'}, svg);
    const regions = {};
    rl.forEach((r, k) => { if (r >= 0) { const o = regions[r] || (regions[r] = {n: 0, sx: 0, sy: 0}); o.n++; o.sx += k % nx; o.sy += Math.floor(k / nx); } });
    Object.entries(regions).forEach(([r, o]) => { if (o.n < 12) return;
      const cx = m.l + (o.sx / o.n + 0.5) * cw, cy = m.t + (ny - 1 - o.sy / o.n + 0.5) * chh;
      const half = ruleName(+r).length * 3.4 + 4;  // about half the label width at 12px
      S('text', {x: Math.min(Math.max(cx, m.l + half), m.l + pw - half), y: cy, 'text-anchor': 'middle', class: 'rulelabel'}, svg, ruleName(+r)); });
    // direct labels: the value of every large region with one score (rule regions carry the rule's label instead)
    const vals = diff ? z.map((v, k) => z2[k] - v) : z;
    const comp = new Int32Array(nx * ny).fill(-1);
    const placed = [];
    for (let s0 = 0; s0 < nx * ny; s0++) {
      if (comp[s0] >= 0) continue;
      const stack = [s0], cells = []; comp[s0] = s0;
      while (stack.length) {
        const k = stack.pop(), i = k % nx, j = (k - i) / nx; cells.push(k);
        for (const [di, dj] of [[1, 0], [-1, 0], [0, 1], [0, -1]]) {
          const a = i + di, b = j + dj; if (a < 0 || a >= nx || b < 0 || b >= ny) continue;
          const q = b * nx + a; if (comp[q] < 0 && vals[q] === vals[k] && rl[q] === rl[k]) { comp[q] = s0; stack.push(q); }
        }
      }
      if (rl[s0] >= 0 || cells.length * cw * chh < 1800) continue;
      // label compact regions only: a continuous scorer makes thin diagonal bands, where labels would pile up
      let i0 = nx, i1 = 0, j0 = ny, j1 = 0;
      cells.forEach(k => { const i = k % nx, j = Math.floor(k / nx); i0 = Math.min(i0, i); i1 = Math.max(i1, i); j0 = Math.min(j0, j); j1 = Math.max(j1, j); });
      const bw = (i1 - i0 + 1), bh = (j1 - j0 + 1);
      if (cells.length / (bw * bh) < 0.6 || bw * cw < 28 || bh * chh < 16) continue;
      let sx = 0, sy = 0; cells.forEach(k => { sx += k % nx; sy += Math.floor(k / nx); });
      const cx = sx / cells.length, cy = sy / cells.length;
      let best = cells[0], bd = Infinity;
      cells.forEach(k => { const d = ((k % nx) - cx) ** 2 * cw * cw + (Math.floor(k / nx) - cy) ** 2 * chh * chh; if (d < bd) { bd = d; best = k; } });
      const bi = best % nx, bj = Math.floor(best / nx), v = vals[s0];
      const lx = m.l + (bi + 0.5) * cw, ly = m.t + (ny - 1 - bj + 0.5) * chh + 4;
      if (placed.some(([x, y]) => Math.abs(x - lx) < 26 && Math.abs(y - ly) < 14)) continue;
      placed.push([lx, ly]);
      S('text', {x: lx, y: ly, 'text-anchor': 'middle', class: 'cellval'}, svg,
        diff ? (v > 0 ? '+' : v < 0 ? '−' : '') + Math.abs(v) : v);
    }
    // axes
    let lastX = -1e9;
    hd.xTicks.filter(([i]) => { const x = (i + 0.5) * cw; if (x - lastX < 40) return false; lastX = x; return true; }).forEach(([i, t]) => S('text', {x: m.l + (i + 0.5) * cw, y: m.t + ph + 15, 'text-anchor': 'middle', class: 'axlabel'}, svg, t));
    hd.yTicks.forEach(([j, t]) => S('text', {x: m.l - 6, y: m.t + (ny - 1 - j + 0.5) * chh + 4, 'text-anchor': 'end', class: 'axlabel'}, svg, t));
    S('text', {x: m.l + pw, y: m.t + ph + 34, 'text-anchor': 'end', class: 'axlabel'}, svg, hd.xLabel + ' →');
    S('text', {x: m.l, y: m.t + ph + 34, 'text-anchor': 'start', class: 'axlabel'}, svg, '↑ ' + hd.yLabel);
    const hov = S('rect', {width: cw, height: chh, class: 'hover', visibility: 'hidden'}, svg);
    svg.addEventListener('pointermove', e => {
      const b = svg.getBoundingClientRect(), px = (e.clientX - b.left) * W / b.width, py = (e.clientY - b.top) * Ht / b.height;
      const i = Math.floor((px - m.l) / cw), jj = Math.floor((py - m.t) / chh);
      if (i < 0 || i >= nx || jj < 0 || jj >= ny) { hov.setAttribute('visibility', 'hidden'); hideTip(); return; }
      const j = ny - 1 - jj, k = j * nx + i;
      hov.setAttribute('x', m.l + i * cw); hov.setAttribute('y', m.t + jj * chh); hov.setAttribute('visibility', 'visible');
      const rows = [{value: `${hd.xLabel.replace(/ \(.*\)/, '')}: ${fmt(hd.xFmt, hd.xs[i])}`}, {label: `${hd.yLabel.replace(/ \(.*\)/, '')}: ${fmt(hd.yFmt, hd.ys[j])}`}];
      labels.forEach((l, si) => { rows.push({key: si, value: String(hd.z[l][k]), label: (labels.length > 1 ? l + ' · ' : '') + (ruleName(hd.rule[l][k]) || 'kural yok')});
        rows.push({label: D.factors[l].map((f, n) => `${D.factorShort[f] || f} ${hd.factors[l][k][n]}`).join(' · '), muted: true}); });
      showTip(rows, e.clientX, e.clientY);
    });
    svg.addEventListener('pointerleave', () => { hov.setAttribute('visibility', 'hidden'); hideTip(); });
  }
  function drawAll() {
    D.heat.forEach(draw);
    document.querySelectorAll('.heat-scale').forEach(el => { el.hidden = view === 'fark'; });
    document.querySelectorAll('.diff-scale').forEach(el => { el.hidden = view !== 'fark'; });
  }
  window.addEventListener('resize', debounce(drawAll, 150));
  drawAll();
})();
})();
"""


def model_section(m: dict, labels: list[str]) -> str:
    parts = []
    for spec, formulas in ((FLOW_V2, formulas_v2_html), (FLOW_V3, formulas_v3_html)):
        check = m["flow"].get(spec["name"])
        if check is None:
            continue
        status = "uyumlu" if not check["issues"] else "uyumsuz: " + "; ".join(check["issues"])
        notes = (" Şemada olup bu örnekte hiç gözlenmeyen yollar: " + "; ".join(check["notes"]) + "."
                 if check["notes"] else "")
        title = {"v2": "v2: basamaklı faktörler ve TL kuralları",
                 "v3": "v3: doğrusal paylar, ödeme gücü tavanı, servet pisti"}[spec["name"]]
        if check["scorer"] != spec["name"]:
            title += f" ({check['scorer']} puanlayıcısı)"
        parts.append(f"<h3>{esc(title)}</h3>{formulas()}"
                     f"<p class='hint'>Bir kutunun üzerine gelin ya da sekmeyle odaklanın: o kutudan geçen yol vurgulanır. "
                     f"Şema elle çizildi ve bölüm 2'deki ölçülmüş bağımlılık matrisiyle denetlendi: {esc(status)}.{esc(notes)}</p>"
                     f"<div class='card flowbox'>{flow_svg(spec)}</div>")
    return "".join(parts) + "<p class='hint'>Metin karşılığı: formüller ve bölüm 2'deki matris.</p>"


def build_page(m: dict, scorers: list[Scorer]) -> str:
    labels = [s.label for s in scorers]
    first = labels[0]
    js_data = {
        "scorers": [{"label": s.label, "path": shown_path(s.dll)} for s in scorers],
        "inputs": [{"key": k, "name": n, "short": sh, "money": k in MONEY} for k, n, sh, _ in INPUTS],
        "factors": m["factorKeys"], "factorShort": FACTOR_TR, "rules": m["rules"], "ruleNames": RULE_TR,
        "segmentMin": {"MEDIUM": m["params"]["segments"][first].get("MEDIUM", [41])[0],
                       "HIGH": m["params"]["segments"][first].get("HIGH", [71])[0]},
        "personas": m["personas"], "sweeps": m["sweeps"], "heat": m["heat"],
    }
    data = json.dumps(js_data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    scorer_text = " · ".join(f"{esc(s.label)} ({esc(s.version)}): <code>{esc(shown_path(s.dll))}</code>" for s in scorers)
    ramp = "".join(f'<span style="background:var(--q{i})"></span>' for i in range(13))
    heats = []
    for h in m["heat"]:
        title = "Tasarruf oranı × rezerv ayı" if h["id"] == "heat-sr" else "Gelir × net servet (kural bölgeleri çerçeveli)"
        heats.append(f'<h3>{esc(title)}</h3><p class="hint">{esc(h["fixed"])}</p><div class="card"><div class="chart" id="{h["id"]}"></div></div>'
                     f'{heat_table(h, labels)}')
    persona_rows = []
    for p in m["personas"]:
        cells = "".join(f"<td class='n'>{p['results'][l]['score']} <span class='hint'>{p['results'][l]['segment']}"
                        f"{' · ' + esc(p['results'][l]['rule']) if p['results'][l]['rule'] else ''}</span></td>" for l in labels)
        persona_rows.append(f"<tr><th>{esc(p['label'])}<div class='hint'>{esc(p['description'])}</div></th>"
                            + "".join(f"<td class='n'>{money_short(p['profile'][k])}</td>" for k in MONEY)
                            + f"<td class='n'>{p['profile']['impatienceLevel']}</td>{cells}</tr>")
    personas = table(["Kişi"] + [esc(SHORT_TR[k]) for k in KEYS] + [f"Skor ({esc(l)})" for l in labels], persona_rows,
                     "Demo hesapları: infra/seed/seed_demo_users.py (playground.py'deki hazır profillerle aynı).")
    v3_params = ""
    if labels_with(m, labels, V3_KEYS):
        v3_params = ("<h3>v3 çapaları ve mekanizmaları</h3><p>v3'te eşik yerine çapa var: pay çapalar arasında doğrusal. "
                     "Hangi çapanın kanıta dayandığı öneri belgesinin (IQ_V3_PROPOSAL.md) 8.3 bölümünden.</p>"
                     + params_v3_html(m, labels))
    sections = []
    if len(labels) > 1:
        sections.append(("ozet", "Özet: " + " ve ".join(labels),
                         "<p>Aynı profiller her puanlayıcıyla ayrı skorlandı; aşağıdaki her sayı puanlayıcıların çıktısından.</p>"
                         + summary_html(m, labels)))
    sections += [
        ("model", "1. Biçimsel model", model_section(m, labels)),
        ("matris", "2. Bağımlılık matrisi ve etkin ağırlıklar",
         "<p>Hangi girdi hangi faktöre dokunuyor? Hücre: girdi değişince o faktör puanının değiştiği sınama payı "
         "(koyu = sık). Son sütun, girdinin dokunduğu faktörlerin en yüksek puanlarının toplamı: o girdinin skorda "
         "oynatabildiği puan. Her puanlayıcı kendi faktörleriyle gösteriliyor.</p>" + deps_html(m, labels)
         + "<h3>Nominal ve etkin ağırlık</h3><p>Nominal ağırlık faktörün en yüksek puanı. Etkin ağırlık, skor varyansının o "
         "faktörden gelen payı: dağılımı geniş ve skorla birlikte oynayan faktör nominal payından fazlasını taşır.</p>"
         + weights_html(m, labels)),
        ("parametreler", "3. Parametreler ve dayanakları",
         "<h3>v2 eşikleri</h3><p>Her parametrenin değeri, anlamı, kaynağı ve kanıt düzeyi. Sınama sütunları eşiğin kodda "
         "gerçekten orada olduğunu gösterir.</p>" + params_html(m, labels) + v3_params),
        ("tarama", "4. Tek girdi taramaları",
         "<p>Diğer girdiler sabitken bir girdi değişir. v2'nin basamakları uçurumdur: 2 puan ve üstü sıçramalar eksende ▲ "
         "ile işaretli, en büyükleri üzerinde yazılı, konumları ikinci bir puanlama turuyla birkaç TL'ye kadar inceltildi. "
         "Fare ya da ok tuşlarıyla gezin; tablo görünümünde her skor aralığı var.</p>" + personas +
         '<div class="controls"><label>Kişi <select id="sw-persona"></select></label>'
         '<label>Girdi <select id="sw-input"></select></label></div>'
         + legend(labels) + '<div class="card"><div id="sw-info" class="hint"></div><div class="chart" id="sw-chart"></div></div>'
         '<details class="tv"><summary>Tablo görünümü</summary><div id="sw-table"></div></details>'),
        ("ucurum", "5. Uçurum haritası", f"<p>Örnek nüfusun (bölüm 7'deki dağılım, {num(2 * m['sobolN'])} profil) her profilinde "
         "her parasal girdi tek tek %1 azaltılıp artırıldı. Her profil için en büyük |Δskor| alındı.</p>"
         + cliffs_html(m, labels)),
        ("isi", "6. İki boyutlu ısı haritaları",
         '<div class="controls" id="heat-switch" hidden><span class="hint">Gösterilen:</span><span class="seg"></span></div>'
         f'<div class="scale heat-scale"><span>skor 0</span><span class="ramp" aria-hidden="true">{ramp}</span><span>100</span>'
         f'<span>· LOW ≤ 40 &lt; MEDIUM ≤ 70 &lt; HIGH · çerçeve = kural ya da etiket bölgesi</span></div>'
         '<div class="scale diff-scale" hidden><span>mavi: ikinci puanlayıcı yüksek · gri: aynı · kırmızı: düşük</span></div>'
         + "".join(heats)),
        ("sobol", "7. Global duyarlılık (Sobol)",
         f"<p>Saltelli örneklemesi: iki bağımsız matris A ve B (N = {num(m['sobolN'])}, 7 girdi) ve her girdi için A'nın o "
         f"sütunu B'den alınmış AB<sub>i</sub>; puanlayıcı başına {num(m['sobol'][first]['evaluations'])} puanlama. Birinci derece "
         "S<sub>i</sub> (Saltelli 2010) girdinin tek başına açıkladığı varyans payı; toplam S<sub>Ti</sub> (Jansen 1999) "
         "etkileşimler dahil payı. S<sub>Ti</sub> − S<sub>i</sub> büyükse girdi etkisini başka girdilerle birlikte "
         f"gösteriyor (basamaklar, min()/max() ve tavan bunu üretir). Aralıklar {num(m['bootstrap'])} bootstrap tekrarından.</p>"
         + sobol_html(m, labels)),
        ("ucuz", "8. En ucuz +10 puan", "<p>Her demo kişisi için skoru 10 puan artıran tek girdi değişiklikleri.</p>"
         + cheapest_html(m, labels)),
        ("anlam", "9. Ne anlama geliyor, bilinen zayıflıklar", weaknesses_html(m, labels)
         + "<h3>Canlı deneme</h3><p>Bir profili elle değiştirip skoru, faktörleri ve AI açıklamasını görmek için: "
         "<code>services/ai-rag-service/venv/Scripts/python evaluation/playground.py</code> → "
         "<a href='http://127.0.0.1:8090'>http://127.0.0.1:8090</a> (yalnız yerel; üründeki C# kurallarıyla puanlar).</p>"),
    ]
    nav = "".join(f'<a href="#{k}">{esc(t)}</a>' for k, t, _ in sections)
    body = "".join(f'<section id="{k}"><h2>{esc(t)}</h2>{content}</section>' for k, t, content in sections)
    total = sum(s.scored for s in scorers)
    procs = sum(s.processes for s in scorers)
    versions = " ve ".join(labels)
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Financial IQ Modeli</title><style>{STYLE}</style></head>
<body><main>
<div class="top"><div><h1>Financial IQ girdi–çıktı modeli: {esc(versions)}</h1>
<div class="hint">Üretildi: {date.today().strftime('%d.%m.%Y')} · skorlar üründeki C# kurallarından (FinancialIQ.BatchScorer):
{scorer_text} · {num(total)} puanlama, {procs} süreç · <code>py -3 evaluation/iq_model.py</code> ile yeniden üretilir, elle
düzenlenmez.</div></div><button class="theme" id="theme" type="button">Tema: sistem</button></div>
<p>Skorun yedi girdiden nasıl oluştuğu: ara oranlar, puan fonksiyonları, toplam, kurallar ve segment. v2 basamaklı
fonksiyonlar ve TL kuralları kullanıyor; v3 doğrusal paylar, bir ödeme gücü tavanı ve bir servet pisti. Sayfadaki her skor
puanlayıcıların çıktısı; tarayıcıda ya da Python'da skor hesabı yok. Yöntem notları: <code>evaluation/IQ_MODEL.md</code>.</p>
{tiles_html(m, labels)}
<nav>{nav}</nav>
{body}
</main><div id="tip" role="status" aria-live="polite"></div>
<script type="application/json" id="iq-data">{data}</script>
<script>{SCRIPT}</script>
</body></html>
"""


def parse_scorer(text: str) -> tuple[str, Path]:
    label, sep, path = text.partition("=")
    if not sep or not label or not path:
        raise argparse.ArgumentTypeError("expected LABEL=PATH, e.g. v3=../other/services/financial-iq-service/src/FinancialIQ.BatchScorer")
    return label, Path(path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--scorer", action="append", type=parse_scorer, metavar="LABEL=PATH",
                    help="BatchScorer dll or project to score with (repeatable; default v2=<this repo's Release build>)")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sobol-n", type=int, default=1024, help="base sample size N (N x 9 scorings)")
    ap.add_argument("--bootstrap", type=int, default=300)
    args = ap.parse_args()
    specs = args.scorer or DEFAULT_SCORERS
    if len({l for l, _ in specs}) != len(specs):
        sys.exit("scorer labels must be unique")

    OUT.mkdir(exist_ok=True)
    scorers = [Scorer(label, path) for label, path in specs]
    model = Model(scorers, args.seed, args.sobol_n, args.bootstrap)
    model.build_pass1()
    print(f"pass 1: {len(model.batch.items)} profiles per scorer")
    model.run_pass1()
    model.run_pass2()

    deps = model.dep_data()
    m = {
        "rules": model.rules, "factorKeys": model.factor_keys, "factorMax": model.factor_max,
        "sobolN": args.sobol_n, "bootstrap": args.bootstrap,
        "personas": model.persona_data(), "sweeps": model.sweep_data(), "cheapest": model.cheapest_data(),
        "sobol": model.sobol_data(), "cliffs": model.cliff_data(), "deps": deps, "heat": model.heat_data(),
        "params": model.param_data(), "witnesses": model.witness_data(),
    }
    m["flow"] = model.check_flow(deps)
    summary = {k: m[k] for k in ("rules", "factorKeys", "factorMax", "sobolN", "sobol", "cliffs", "deps", "params",
                                 "witnesses", "cheapest", "flow")}
    summary["parameters"] = {"seed": args.seed, "sobolN": args.sobol_n, "bootstrap": args.bootstrap,
                             "scorers": {s.label: shown_path(s.dll) for s in scorers},
                             "scored": {s.label: s.scored for s in scorers}, "processes": {s.label: s.processes for s in scorers}}
    (OUT / "iq_model_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    PAGE.write_text(build_page(m, scorers), encoding="utf-8")

    for s in scorers:
        sob = m["sobol"][s.label]
        cl = m["cliffs"][s.label]
        print(f"[{s.label}] scored {s.scored} profiles in {s.processes} processes")
        print("  Sobol (S1 / ST): " + ", ".join(f"{SHORT_TR[r['input']]} {r['S1']:.3f}/{r['ST']:.3f}"
                                                 for r in sorted(sob["rows"], key=lambda r: -r["ST"])))
        print(f"  sum S1 {sob['sumS1']:.3f}; rules {sob['rules']}")
        print(f"  cliffs: max {cl['max']}, share >=5: {cl['atLeast'][5]:.3f}, >=10: {cl['atLeast'][10]:.3f}")
        print("  reach: " + ", ".join(f"{SHORT_TR[k]} {m['deps'][s.label]['matrix'][k]['__reach']}" for k in KEYS))
        print("  witnesses: " + ", ".join(str(w["results"][s.label]["delta"]) for w in m["witnesses"]))
    for name, check in m["flow"].items():
        print(f"flow {name} vs {check['scorer']}: " + ("ok" if not check["issues"] else "; ".join(check["issues"]))
              + (f" (not exercised: {'; '.join(check['notes'])})" if check["notes"] else ""))
    print(f"wrote {PAGE}")


if __name__ == "__main__":
    main()
