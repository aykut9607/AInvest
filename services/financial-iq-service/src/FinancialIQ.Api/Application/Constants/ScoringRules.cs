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

    // written into factorBreakdown.version; raise it whenever a factor, threshold or rule changes so stored results
    // can be told apart (v1 = 6 factors incl. RiskAlignment, v2 = 5 factors, no self-reported risk)
    public const string ScoringVersion = "v2";
}
