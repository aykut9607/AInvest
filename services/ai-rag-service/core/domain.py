# Single source for what the other services can send us. Everything a language model sees is built from these tables,
# so a client cannot smuggle free text (or instructions) into a prompt.
# Financial IQ contracts: contracts/schemas/factor-breakdown.v2.schema.json (production) and scoring v3, variant
# v3c-i5 (evaluation/IQ_V3_PROPOSAL.md section 8, reference evaluation/iq_v3/scoring.py). Both are accepted: the
# history of a user keeps v2 results after v3 goes live, and the AI has to ship before the IQ service switches.

from decimal import Decimal

# A breakdown names the rules that produced it in "version"; a missing version means v2 (v1 had a sixth factor and
# is rejected by the factor check). Everything below that differs between the versions is keyed by this name.
DEFAULT_SCORING_VERSION = "v2"

# factor key from the IQ service -> (Turkish label, maximum points). Keep in sync with FinancialIqCommandManager.
# Scoring v2: the self-reported risk (RiskAlignment) is gone, its points went to the first three factors.
FACTORS: dict[str, tuple[str, int]] = {
    "CashReserveMonths": ("Nakit rezervi", 25),
    "DebtToIncomeRatio": ("Borç/gelir oranı", 25),
    "SavingsRate": ("Tasarruf oranı", 25),
    "ExpenseRatio": ("Gider/gelir oranı", 15),
    "Impatience": ("Sabır", 10),
}

# Scoring v3 (v3c-i5): no expense ratio (it counted the savings rate twice), the debt factor split into the
# installment and the net debt. These maximums are the default; a breakdown that carries factorMaximums wins.
FACTORS_V3: dict[str, tuple[str, int]] = {
    "CashReserveMonths": ("Nakit rezervi", 30),
    "InstallmentToIncome": ("Taksit/gelir oranı", 25),
    "NetDebtToIncome": ("Net borç/gelir oranı", 10),
    "SavingsRate": ("Tasarruf oranı", 30),
    "Impatience": ("Sabır", 5),
}

FACTORS_BY_VERSION: dict[str, dict[str, tuple[str, int]]] = {"v2": FACTORS, "v3": FACTORS_V3}

# extra wording for the prompt only, where a short label was misread by the model
FACTOR_HINTS: dict[str, str] = {
    "Impatience": "acele etmeden bekleyebilme; zayıf ise kullanıcı sabırsızdır",
}

# warning text from the IQ service -> Turkish wording. Unknown warnings are dropped, never passed through.
# The v2 texts keep their meaning in v3; v3 adds a milder text next to each severe one and four consistency checks.
WARNINGS: dict[str, str] = {
    "Low cash reserve": "Nakit rezervi düşük",
    "High debt burden": "Taksit yükü yüksek",
    "High total debt": "Toplam borç yüksek",
    "Negative savings rate": "Tasarruf oranı negatif",
    "Overspending relative to income": "Giderler gelire göre çok yüksek",
    "High impatience": "Sabırsızlık yüksek",
    "Extreme total debt": "Toplam borç aşırı yüksek",
    # scoring v3
    "Elevated debt burden": "Taksit yükü dikkat gerektiren düzeyde",
    "Elevated total debt": "Toplam borç dikkat gerektiren düzeyde",
    "Low savings rate": "Tasarruf oranı düşük",
    "High expense ratio": "Gider oranı yüksek",  # variant v3a only; kept so a v3a result would read the same
    "Installment below interest": "Taksit, borcun tahmini faizini karşılamıyor",
    "Expenses look too low": "Bildirilen gider gerçekçi olamayacak kadar düşük",
    "Installment without debt": "Borç yokken taksit bildirilmiş",
    "Installment exceeds total debt": "Taksit toplam borçtan büyük",
}

# which warnings each version can produce; anything else in a breakdown is dropped like an unknown text
WARNINGS_BY_VERSION: dict[str, frozenset[str]] = {
    "v2": frozenset({"Low cash reserve", "High debt burden", "High total debt", "Negative savings rate",
                     "Overspending relative to income", "High impatience", "Extreme total debt"}),
    # v3c-i5 has no expense ratio, so neither of its two texts can appear
    "v3": frozenset({"Low cash reserve", "High debt burden", "Elevated debt burden", "High total debt",
                     "Elevated total debt", "Negative savings rate", "Low savings rate", "High impatience",
                     "Extreme total debt", "Installment below interest", "Expenses look too low",
                     "Installment without debt", "Installment exceeds total debt"}),
}

SEGMENT_TR = {"LOW": "DÜŞÜK", "MEDIUM": "ORTA", "HIGH": "YÜKSEK"}
LEVEL_TR = {"LOW": "düşük", "MEDIUM": "orta", "HIGH": "yüksek"}

# The interpretation is decided here, not by the model: a small model was seen calling a HIGH score "average".
SEGMENT_MEANING = {
    "LOW": "finansal durum zayıf, öncelikli iyileştirme gerekiyor",
    "MEDIUM": "finansal durum dengeli, bazı alanlar güçlendirilmeli",
    "HIGH": "finansal durum güçlü",
}

# appliedRule -> (score the rule sets, meaning). No digits in the wording: the coach may only write the score and 100.
# v2: the rule decides the score. The IQ service then writes every factor at its maximum or at 0 so the bars add up,
#     so those factor values say nothing about the user: the score is explained by the rule alone.
# v3: the label only names a mechanism that moved the factors (score None: it sets nothing). The score is still the
#     sum of real factor points, so the coach explains the factors and the mechanism together.
RULES: dict[str, tuple[int | None, str]] = {
    "VERY_HIGH_INCOME": (100, "aylık gelir çok yüksek ve net borç bir yıllık geliri aşmıyor; "
                              "bu gelirle diğer eksikler kısa sürede kapanır"),
    "VERY_HIGH_WEALTH": (100, "net servet (nakit ve yatırımlardan borç çıkınca kalan) çok yüksek; "
                              "bu servet giderleri uzun yıllar karşılar"),
    "EXTREME_DEBT": (0, "net borç aşırı yüksek; bu borç düzeyinde diğer göstergeler skoru kurtaramaz"),
    "SOLVENCY_CAP": (None, "net borç yıllık gelire göre çok yüksek; bu borç düzeyinde bütün faktörlerin puanı "
                           "ödeme gücü tavanıyla aşağı çekildi"),
    # the IQ writes this label only from five years of expenses on (WEALTH_RUNWAY_LABEL_MIN_YEARS), so the wording
    # says exactly that much; without the label nothing about the runway is said
    "WEALTH_RUNWAY": (None, "likit servet (nakit ve yatırımların yarısından borç çıkınca kalan) giderleri en az beş "
                            "yıl karşılıyor; bu yüzden tasarruf ve taksit puanları servete göre yukarı çekildi"),
}

RULES_BY_VERSION: dict[str, frozenset[str]] = {
    "v2": frozenset({"VERY_HIGH_INCOME", "VERY_HIGH_WEALTH", "EXTREME_DEBT"}),
    "v3": frozenset({"SOLVENCY_CAP", "WEALTH_RUNWAY"}),
}


def rule_sets_score(rule: str | None) -> bool:
    """True for the v2 rules that replace the factors; False for no rule and for the v3 explanatory labels."""
    return rule is not None and RULES[rule][0] is not None


def scoring_version_of(breakdown: object) -> str:
    """Scoring version of a raw factorBreakdown (dict from the IQ service). v2 when it is missing, unknown or there
    is no result at all: the version only changes definitions, and v2 is what production computes today."""
    if isinstance(breakdown, dict) and breakdown.get("version") in FACTORS_BY_VERSION:
        return breakdown["version"]
    return DEFAULT_SCORING_VERSION


# --- scoring v2 thresholds (ScoringRules.cs / FinancialIqCommandManager.cs) -------------------------------------------
# the alerts reuse them so the assistant never contradicts the score
RESERVE_MIN_MONTHS = 3            # below: "Low cash reserve"
RESERVE_GOOD_MONTHS = 6           # full points
INVESTMENT_RESERVE_SHARE = 0.5    # half of the investments counts as emergency reserve
HIGH_INSTALLMENT_RATIO = 0.36     # above: "High debt burden"
HIGH_NET_DEBT_YEARS = 3           # above: "High total debt"
OVERSPENDING_RATIO = 0.80         # above: "Overspending relative to income"
HIGH_IMPATIENCE_LEVEL = 4         # at or above: "High impatience"


# --- scoring v3 (IQ_V3_PROPOSAL.md 8.1-8.5, same constants as evaluation/iq_v3/scoring.py) ---------------------------
# Decimals like the reference and C# decimal, so an amount exactly on an anchor lands on the same side as in the IQ.
def _table(*pairs: tuple[str, str]) -> tuple[tuple[Decimal, Decimal], ...]:
    return tuple((Decimal(x), Decimal(s)) for x, s in pairs)


V3_INVESTMENT_LIQUID_SHARE = Decimal("0.5")   # liquid assets = cash + half of the investments, everywhere
V3_EXPENSE_FLOOR_SHARE = Decimal("0.10")      # expenses below 10 % of income count as 10 % ("Expenses look too low")
V3_RESERVE_TARGET_MONTHS = Decimal(6)         # emergency target; only liquid assets above it offset the debt
V3_MONTHLY_INTEREST = Decimal("0.035")        # debt service is at least this interest (DebtPayoffRules in the IQ)
V3_WARNING_SHARE = Decimal("0.6")             # a factor below 60 % of its maximum always carries a warning

# anchor tables (measure value, share of the factor maximum), ascending; clamped at both ends, linear in between
V3_RESERVE_MONTHS = _table(("0", "0"), ("3", "0.6"), ("6", "1"))
V3_INSTALLMENT_RATIO = _table(("0.10", "1"), ("0.20", "0.6"), ("0.36", "0.2"), ("0.50", "0"))
V3_NET_DEBT_YEARS = _table(("0.5", "1"), ("1", "0.6"), ("3", "0.2"), ("5", "0"))
V3_SAVINGS_RATE = _table(("-0.10", "0"), ("0", "0.2"), ("0.10", "0.6"), ("0.20", "1"))
V3_IMPATIENCE = _table(("1", "1"), ("2", "0.8"), ("3", "0.6"), ("4", "0.2"), ("5", "0"))
V3_SOLVENCY_CAP = _table(("5", "1"), ("15", "0"))      # net debt in years of income -> factor of every factor
V3_RUNWAY_YEARS = _table(("0", "0"), ("25", "1"))      # liquid net worth in years of expenses (the 4 % rule)
# WEALTH_RUNWAY is written only from this runway on (and when the lift adds points); the lift itself starts at 0
V3_WEALTH_RUNWAY_LABEL_MIN_YEARS = Decimal(5)

# severe-text lines of v3 (the v2 texts keep their v2 threshold)
V3_SEVERE_INSTALLMENT_RATIO = Decimal("0.36")   # weak installment above it: "High debt burden", else "Elevated ..."
V3_SEVERE_NET_DEBT_YEARS = Decimal(3)           # weak net debt above it: "High total debt", else "Elevated ..."


def anchor_value(table: tuple[tuple[Decimal, Decimal], ...], share: str) -> Decimal:
    """Measure value at which a table reaches a share, e.g. the 60 % ("adequate") line quoted in alert messages."""
    return next(x for x, s in table if s == Decimal(share))


def factor_level(points: float, maximum: int, version: str = DEFAULT_SCORING_VERSION) -> str:
    """Qualitative label for a factor, so the model does not judge 15/25 on its own.
    v3: "weak" is exactly the warning line (below 60 % of the maximum), so a weak label and a warning go together."""
    share = points / maximum
    if share >= 0.8:
        return "güçlü"
    if share >= (float(V3_WARNING_SHARE) if version == "v3" else 0.5):
        return "orta"
    return "zayıf"


MAX_SCORE = 100

DISCLAIMER = "Bu bilgi yalnızca eğitim amaçlıdır, yatırım tavsiyesi değildir."
