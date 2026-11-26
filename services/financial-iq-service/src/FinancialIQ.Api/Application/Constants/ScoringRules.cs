namespace FinancialIQ.Api.Application.Constants;

// Rules and constants that sit above the 5 factors. The factors compare ratios (reserve months, debt-to-income, ...),
// which works for ordinary amounts but gives odd results at the extremes:
//  - someone earning 1,000,000 a month with no cash yet would lose the whole cash-reserve factor,
//    although a reserve builds up within weeks at that income
//  - someone owing 100,000,000 with an ordinary income could still score well if the monthly installment is small
//  - someone holding 10,000,000 net with a small salary would lose the savings and expense factors,
//    although the wealth alone covers decades of expenses
// So the amounts are NOT capped (any income/debt is accepted); instead these thresholds decide the score directly.
// The values are a first proposal and will be revisited together with the IQ rule table.
public static class ScoringRules
{
    // monthly income at or above this -> score 100, but only while the net debt is at most
    // VeryHighIncomeMaxNetDebtYears of income: a high earner without cash is fine, a high earner deep in debt is not
    public const decimal VeryHighMonthlyIncome = 1_000_000m;
    public const decimal VeryHighIncomeMaxNetDebtYears = 1m;

    // net worth (cash + investments - total debt) at or above this -> score 100, whatever the income
    //example lets say cash is 2,000,000, investments 9,000,000 and debt 1,000,000 -> net worth 10,000,000 -> 100
    public const decimal VeryHighNetWorth = 10_000_000m;

    // net debt above this many years of income: debt factor 0 and the "High total debt" warning
    public const decimal HighNetDebtYears = 3m;
    public const string HighTotalDebtWarning = "High total debt";

    // net debt (total debt - cash - investments) at or above this -> score 0 (unless the monthly income is also very high).
    // Net, not total: 100,000,000 of debt next to 500,000,000 of investments is not a hopeless position
    public const decimal ExtremeNetDebt = 100_000_000m;

    // share of the investments that counts as emergency reserve (factor 1). Investments can be sold when needed,
    // but maybe at a loss or not within days, so only half of them is treated like cash.
    //example lets say cash is 10,000 and investments are 20,000 -> reserve = 10,000 + 20,000 * 0.5 = 20,000
    public const decimal InvestmentReserveShare = 0.5m;

    // value of "appliedRule" in factorBreakdown; null when the normal 5-factor calculation decided the score
    public const string VeryHighIncomeRule = "VERY_HIGH_INCOME";
    public const string VeryHighWealthRule = "VERY_HIGH_WEALTH";
    public const string ExtremeDebtRule = "EXTREME_DEBT";

    public const string ExtremeDebtWarning = "Extreme total debt";

    // written into factorBreakdown.version and the scoring_version column; raise it whenever a factor, threshold or
    // rule changes so stored results can be told apart (v1 = 6 factors incl. RiskAlignment, v2 = 5 factors, no
    // self-reported risk). Each version's full rule set is stored in scoring_rule_versions (ScoringRuleSnapshots);
    // ScoringRuleDocumentTests fails when a number below changes without a new version
    // v2.1 (26 Nov 2026): the same 5 factors, the cliffs between the special rules and the factors removed (adjustments below);
    // income 0 is accepted
    public const string ScoringVersion = "v2.1";

    // --- the 5 factors (v2). Maximums: 25 / 25 / 25 / 15 / 10 = 100 ---

    // 1) months the reserve (cash + half of the investments) covers the monthly expenses
    public static readonly ScoreScale CashReserveMonths = new(
        "(cash + 50% of investments) / monthly expenses, in months",
        ScoreScale.AtLeast,
        [new(6m, 25), new(3m, 15), new(1m, 8)], 0,
        new WarningRule("Low cash reserve", WarningRule.Below, 3m));

    // 2a) monthly installment / monthly income
    public static readonly ScoreScale InstallmentToIncome = new(
        "monthly debt payment / monthly income",
        ScoreScale.AtMost,
        [new(0.10m, 25), new(0.20m, 15), new(0.36m, 8)], 0,
        new WarningRule("High debt burden", WarningRule.Above, 0.36m));

    // 2b) net debt (total debt - cash - investments) in years of income; factor 2 takes the worse of 2a and 2b
    public static readonly ScoreScale NetDebtYearsOfIncome = new(
        "(total debt - cash - investments) / (monthly income x 12), in years",
        ScoreScale.AtMost,
        [new(0.5m, 25), new(1m, 15), new(HighNetDebtYears, 8)], 0,
        new WarningRule(HighTotalDebtWarning, WarningRule.Above, HighNetDebtYears));

    // 3) (income - expenses - installment) / income
    public static readonly ScoreScale SavingsRate = new(
        "(monthly income - expenses - debt payment) / monthly income",
        ScoreScale.AtLeast,
        [new(0.20m, 25), new(0.10m, 15), new(0m, 8)], 0,
        new WarningRule("Negative savings rate", WarningRule.Below, 0m));

    // 4) expenses / income
    public static readonly ScoreScale ExpenseRatio = new(
        "monthly expenses / monthly income",
        ScoreScale.AtMost,
        [new(0.40m, 15), new(0.60m, 9), new(0.80m, 5)], 0,
        new WarningRule("Overspending relative to income", WarningRule.Above, 0.80m));

    // 5) self-reported impatience 1-5 (present bias); level 1 -> 10 ... level 5 -> 0
    public static readonly ScoreScale Impatience = new(
        "self-reported impatience level, 1 (patient) to 5 (impatient)",
        ScoreScale.AtMost,
        [new(1m, 10), new(2m, 8), new(3m, 5), new(4m, 2)], 0,
        new WarningRule("High impatience", WarningRule.Above, 3m));

    // --- adjustments (v2.1): the special rules above were cliffs. 9,900,000 of net worth scored 58 and 10,000,000 scored 100;
    // 999,999 a month scored 33 and 1,000,000 scored 100; 99,000,000 of net debt next to a salary of 40,000 scored 50 and
    // 100,000,000 scored 0. These make the way to those rules continuous. ---

    // net worth that pays every yearly outgoing (expenses + installments) for this many years -> floor 100, proportionally below.
    // 25 years = the 4 % withdrawal rule (Bengen 1994; Cooley, Hubbard, Walz 1998): such a portfolio lasts a lifetime
    public const decimal WealthYearsForFullScore = 25m;
    public const string WealthFloorRule = "WEALTH_FLOOR";

    // floor = 100 x monthly income / VeryHighMonthlyIncome, with the same net-debt condition as VERY_HIGH_INCOME
    public const string IncomeFloorRule = "INCOME_FLOOR";

    // net debt above HighNetDebtYears of income: the score is at most DebtCapAtLimit (inside LOW), minus DebtCapPerYear for every
    // further year; with no income at all a net debt caps the score at 0
    public const int DebtCapAtLimit = 40;
    public const int DebtCapPerYear = 2;
    public const string DebtCapRule = "DEBT_CAP";

    // segment from the total score
    public const int HighSegmentMinScore = 71;
    public const int MediumSegmentMinScore = 41;
}
