# Single source for what the other services can send us. Everything a language model sees is built from these tables,
# so a client cannot smuggle free text (or instructions) into a prompt.
# Financial IQ contract: contracts/schemas/factor-breakdown.v2.schema.json

# factor key from the IQ service -> (Turkish label, maximum points). Keep in sync with FinancialIqCommandManager.
# Scoring v2: the self-reported risk (RiskAlignment) is gone, its points went to the first three factors.
FACTORS: dict[str, tuple[str, int]] = {
    "CashReserveMonths": ("Nakit rezervi", 25),
    "DebtToIncomeRatio": ("Borç/gelir oranı", 25),
    "SavingsRate": ("Tasarruf oranı", 25),
    "ExpenseRatio": ("Gider/gelir oranı", 15),
    "Impatience": ("Sabır", 10),
}

# extra wording for the prompt only, where a short label was misread by the model
FACTOR_HINTS: dict[str, str] = {
    "Impatience": "acele etmeden bekleyebilme; zayıf ise kullanıcı sabırsızdır",
}

# warning text from the IQ service -> Turkish wording. Unknown warnings are dropped, never passed through.
WARNINGS: dict[str, str] = {
    "Low cash reserve": "Nakit rezervi düşük",
    "High debt burden": "Taksit yükü yüksek",
    "High total debt": "Toplam borç yüksek",
    "Negative savings rate": "Tasarruf oranı negatif",
    "Overspending relative to income": "Giderler gelire göre çok yüksek",
    "High impatience": "Sabırsızlık yüksek",
    "Extreme total debt": "Toplam borç aşırı yüksek",
}

SEGMENT_TR = {"LOW": "DÜŞÜK", "MEDIUM": "ORTA", "HIGH": "YÜKSEK"}
LEVEL_TR = {"LOW": "düşük", "MEDIUM": "orta", "HIGH": "yüksek"}

# The interpretation is decided here, not by the model: a small model was seen calling a HIGH score "average".
SEGMENT_MEANING = {
    "LOW": "finansal durum zayıf, öncelikli iyileştirme gerekiyor",
    "MEDIUM": "finansal durum dengeli, bazı alanlar güçlendirilmeli",
    "HIGH": "finansal durum güçlü",
}

# appliedRule -> (score the rule sets, meaning). When a rule decides the score, the IQ service writes every factor at
# its maximum or at 0 so the bars add up, so those factor values say nothing about the user: the score is explained
# by the rule alone. No digits in the wording: the coach may only write the score and 100.
RULES: dict[str, tuple[int, str]] = {
    "VERY_HIGH_INCOME": (100, "aylık gelir çok yüksek ve net borç bir yıllık geliri aşmıyor; "
                              "bu gelirle diğer eksikler kısa sürede kapanır"),
    "VERY_HIGH_WEALTH": (100, "net servet (nakit ve yatırımlardan borç çıkınca kalan) çok yüksek; "
                              "bu servet giderleri uzun yıllar karşılar"),
    "EXTREME_DEBT": (0, "net borç aşırı yüksek; bu borç düzeyinde diğer göstergeler skoru kurtaramaz"),
}

# thresholds the IQ rules use (ScoringRules.cs / FinancialIqCommandManager.cs); the warnings reuse them so the
# assistant never contradicts the score
RESERVE_MIN_MONTHS = 3            # below: "Low cash reserve"
RESERVE_GOOD_MONTHS = 6           # full points
INVESTMENT_RESERVE_SHARE = 0.5    # half of the investments counts as emergency reserve
HIGH_INSTALLMENT_RATIO = 0.36     # above: "High debt burden"
HIGH_NET_DEBT_YEARS = 3           # above: "High total debt"
OVERSPENDING_RATIO = 0.80         # above: "Overspending relative to income"
HIGH_IMPATIENCE_LEVEL = 4         # at or above: "High impatience"


def factor_level(points: float, maximum: int) -> str:
    """Qualitative label for a factor, so the model does not judge 15/25 on its own."""
    share = points / maximum
    if share >= 0.8:
        return "güçlü"
    if share >= 0.5:
        return "orta"
    return "zayıf"


MAX_SCORE = 100

DISCLAIMER = "Bu bilgi yalnızca eğitim amaçlıdır, yatırım tavsiyesi değildir."
