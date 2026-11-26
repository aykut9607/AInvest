namespace FinancialIQ.Api.Application.Constants;

// Scoring v3 (variant v3c-i5, evaluation/IQ_V3_PROPOSAL.md): 5 factors 30 / 25 / 10 / 30 / 5, every factor a
// piecewise-linear share of its maximum, no TL thresholds. v2 decided extreme amounts with three TL rules
// (VERY_HIGH_INCOME, VERY_HIGH_WEALTH, EXTREME_DEBT); 1 TL across one of those lines moved the score by up to 100.
// v3 replaces them with two continuous mechanisms that only depend on ratios:
//  - the solvency cap scales every factor down while the net debt grows from 5 to 15 years of income
//  - the wealth runway (liquid net worth in years of expenses) lifts the cash-flow factors of someone who could live
//    off their wealth
// so the same finances at 30% higher prices score exactly the same, and 1 TL never moves the score by more than 1.
// The rules of v1 and v2 are kept as frozen documents in ScoringRuleSnapshots (results calculated with them point there).
public static class ScoringRules
{
    // written into factorBreakdown.version and the scoring_version column; raise it whenever a factor, anchor or
    // rule changes so stored results can be told apart (v1 = 6 factors incl. RiskAlignment, v2 = 5 step factors and
    // three TL rules, v3 = 5 linear factors, solvency cap and wealth runway). Each version's full rule set is stored
    // in scoring_rule_versions (ScoringRuleSnapshots); ScoringRuleDocumentTests fails when a number below changes
    // without a new version
    public const string ScoringVersion = "v3";

    // --- the measures (FinancialIqCommandManager.Measure) ---

    // half of the investments counts as liquid (Basel LCR level-2B haircut: they can be sold, maybe at a loss).
    // The same liquid assets are used for the reserve, the debt offset and the wealth runway, so no lira counts twice
    //example lets say cash is 10,000 and investments are 20,000 -> liquid assets = 10,000 + 20,000 * 0.5 = 20,000
    public const decimal InvestmentLiquidShare = 0.5m;

    // expenses below 10% of the income are treated as 10% in the savings rate (and flagged)
    //example lets say income is 50,000 and expenses 0 -> effective expenses 5,000
    public const decimal ExpenseFloorShare = 0.10m;

    // the expenses the reserve months, the 6-month target and the wealth runway are measured in are at least 2,000 TL:
    // a data-quality floor (0 expenses would make any reserve infinite), not a score threshold. Until 26 Nov the 10%
    // income floor sat there too, so more income raised the denominator and LOWERED the score when the expenses were
    // below 10% of the income (income 100,000 -> 200,000 with expenses 5,000 and cash 60,000: 100 -> 88)
    //example lets say expenses are 500 -> the reserve is measured in months of 2,000
    public const decimal ExpenseFloorTl = 2000m;

    // the emergency target in months of outflow; only the liquid assets above it are taken off the debt
    //example lets say the outflow is 20,000 a month and the liquid assets 150,000 -> 30,000 above the target lower the debt
    public const decimal ReserveTargetMonths = 6m;

    // the debt service is at least the interest the net debt accrues; a smaller installment means the debt grows.
    // Same assumption as DebtPayoffRules.DefaultMonthlyInterestRate (kept separate so the payoff default can change
    // without changing the score)
    //example lets say the net debt is 2,000,000 and the installment 2,000 -> effective installment 70,000
    public const decimal InterestFloorMonthlyRate = 0.035m;

    // --- the 5 factors. Maximums: 30 / 25 / 10 / 30 / 5 = 100 ---
    // every scale sits on the same ladder: ideal benchmark -> 100%, adequate -> 60% (the warning line),
    // fragile -> 20%, collapse -> 0%

    // 1) months the liquid assets cover the monthly outflow (expenses + installment); 3 months 60%, 6 months 100%
    public static readonly ScoringFactor CashReserveMonths = new("CashReserveMonths", 30,
        new LinearScale("reserveMonths", [new(0m, 0m), new(3m, 0.6m), new(6m, 1m)]),
        LiftedByWealthRunway: false,
        new FactorWarning("Low cash reserve"));

    // 2) effective installment / income; 10% 100%, 20% 60%, 36% 20% (the 28/36 rule), 50% 0
    public static readonly ScoringFactor InstallmentToIncome = new("InstallmentToIncome", 25,
        new LinearScale("installmentRatio", [new(0.10m, 1m), new(0.20m, 0.6m), new(0.36m, 0.2m), new(0.50m, 0m)]),
        LiftedByWealthRunway: true,
        new FactorWarning("Elevated debt burden", new WarningRule("High debt burden", WarningRule.Above, 0.36m)));

    // 3) net debt in years of income; 0.5 years 100%, 1 year 60%, 3 years 20%, 5 years 0
    public static readonly ScoringFactor NetDebtToIncome = new("NetDebtToIncome", 10,
        new LinearScale("netDebtYears", [new(0.5m, 1m), new(1m, 0.6m), new(3m, 0.2m), new(5m, 0m)]),
        LiftedByWealthRunway: false,
        new FactorWarning("Elevated total debt", new WarningRule("High total debt", WarningRule.Above, 3m)));

    // 4) (income - effective expenses - effective installment) / income; -10% 0, 0 20%, 10% 60%, 20% 100%
    public static readonly ScoringFactor SavingsRate = new("SavingsRate", 30,
        new LinearScale("savingsRate", [new(-0.10m, 0m), new(0m, 0.2m), new(0.10m, 0.6m), new(0.20m, 1m)]),
        LiftedByWealthRunway: true,
        new FactorWarning("Low savings rate", new WarningRule("Negative savings rate", WarningRule.Below, 0m)));

    // 5) self-reported impatience 1-5 (present bias); level 3 is the neutral answer (60%, no warning)
    public static readonly ScoringFactor Impatience = new("Impatience", 5,
        new LinearScale("impatienceLevel", [new(1m, 1m), new(2m, 0.8m), new(3m, 0.6m), new(4m, 0.2m), new(5m, 0m)]),
        LiftedByWealthRunway: false,
        new FactorWarning("High impatience"));

    // display order: factorBreakdown.factors and factorMaximums are written in this order
    public static readonly IReadOnlyList<ScoringFactor> Factors =
        [CashReserveMonths, InstallmentToIncome, NetDebtToIncome, SavingsRate, Impatience];

    // --- above the factors ---

    // solvency cap: every factor's points are multiplied by this share of the net debt in years of income.
    // At 36% of the income (the fragility line) without interest, 5 years of debt take ~14 years to repay, 15 years ~42
    //example lets say the net debt is 10 years of income -> every factor keeps half of its points
    public static readonly LinearScale SolvencyCap = new("netDebtYears", [new(5m, 1m), new(15m, 0m)]);

    // wealth runway: liquid net worth in years of reserve expenses (max(expenses, ExpenseFloorTl)); 25 years = the 4% rule (Bengen 1994).
    // Its share is a floor for the cash-flow factors (InstallmentToIncome, SavingsRate)
    //example lets say the runway is 10 years -> share 0.4 -> the savings factor gets at least 0.4 * 30 = 12 points
    public static readonly LinearScale WealthRunway = new("runwayYears", [new(0m, 0m), new(25m, 1m)]);

    // the WEALTH_RUNWAY label needs a runway of at least 5 years (a fifth of the full lift). The lift itself starts at
    // 0 years, but a few months of cash that round a factor up by 1 point are not "the wealth covers the expenses for
    // years", so they get no label. Written on the years, not on the share, so 5 years exactly gets the label
    //example lets say the runway is 0.42 years and lifts the score from 25 to 26 -> no label; 30 years, 68 -> 98 -> WEALTH_RUNWAY
    public const decimal WealthRunwayLabelMinYears = 5m;

    // a factor below 60% of its maximum (points before the cap) always carries its warning, at 60% or above never
    public const decimal WarningShare = 0.6m;

    // points = maximum * share * cap, rounded half up per factor: first to 6 decimals (absorbs the last-digit noise
    // of a division, so a value that is x.5 on paper rounds up), then to an integer. The score is their sum
    public const int PointsPreRoundingDecimals = 6;

    // value of "appliedRule" in factorBreakdown: only a label that explains the score, never a rule that sets it
    public const string SolvencyCapRule = "SOLVENCY_CAP";
    public const string WealthRunwayRule = "WEALTH_RUNWAY";

    // warnings that are not tied to one factor (after the factor warnings, in this order)
    public const string ExtremeDebtWarning = "Extreme total debt";
    public const string InstallmentBelowInterestWarning = "Installment below interest";
    public const string ExpensesTooLowWarning = "Expenses look too low";
    public const string InstallmentWithoutDebtWarning = "Installment without debt";
    public const string InstallmentExceedsDebtWarning = "Installment exceeds total debt";

    // segment from the total score (unchanged since v1)
    public const int HighSegmentMinScore = 71;
    public const int MediumSegmentMinScore = 41;
}
