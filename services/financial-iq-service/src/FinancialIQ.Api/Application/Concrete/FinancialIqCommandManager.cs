using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Application.Results;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Infrastructure.Abstract;
using System.Text.Json;

namespace FinancialIQ.Api.Application.Concrete;

// CQRS-lite write side: validation, the scoring rules and saving. The reads are in FinancialIqQueryManager.
public class FinancialIqCommandManager : IFinancialIqCommandService
{
    private readonly IFinancialIqResultDal _dal;

    // the most each factor can give (sum = 100); used when a rule in ScoringRules decides the score.
    // v2: the self-reported risk (RiskAlignment, 15 points) is gone, its points went to the first three factors
    // Read from the scales in ScoringRules, so a changed tier changes the maximum too
    internal static readonly IReadOnlyDictionary<string, decimal> FactorMaximums = new Dictionary<string, decimal>
    {
        ["CashReserveMonths"] = ScoringRules.CashReserveMonths.MaxPoints,
        // the factor is the worse of the two parts, so it can never be more than the smaller maximum
        ["DebtToIncomeRatio"] = Math.Min(ScoringRules.InstallmentToIncome.MaxPoints, ScoringRules.NetDebtYearsOfIncome.MaxPoints),
        ["SavingsRate"] = ScoringRules.SavingsRate.MaxPoints,
        ["ExpenseRatio"] = ScoringRules.ExpenseRatio.MaxPoints,
        ["Impatience"] = ScoringRules.Impatience.MaxPoints
    };

    public FinancialIqCommandManager(IFinancialIqResultDal dal)
    {
        _dal = dal;
    }

    public async Task<IDataResult<FinancialIqResultResponse>> CalculateAsync(CalculateRequest request)
    {
        // without a user id the result could not be found again (and empty ids would all share one row)
        if (string.IsNullOrWhiteSpace(request.UserId) || request.UserId.Length > FinancialIqResult.UserIdMaxLength)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidUserId);

        // 0 is a valid amount everywhere (a student, someone out of work); only negative amounts are refused
        if (request.MonthlyIncome < 0 || request.MonthlyExpenses < 0 || request.MonthlyDebtPayment < 0 || request.CashReserve < 0 || request.TotalDebt < 0 || request.InvestmentAmount < 0)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.NegativeAmountNotAllowed);

        if (request.ImpatienceLevel < 1 || request.ImpatienceLevel > 5)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidImpatienceLevel);

        var (score, segment, factorBreakdown) = CalculateScore(request);


        var entity = new FinancialIqResult
        {
            UserId = request.UserId,
            Score = score,
            Segment = segment,
            FactorBreakdown = factorBreakdown,
            ScoringVersion = ScoringRules.ScoringVersion,
            UpdatedAt = DateTime.UtcNow
        };

        await _dal.SaveAsync(entity);

        var saved = await _dal.GetAsync(x => x.UserId == request.UserId);
        return new SuccessDataResult<FinancialIqResultResponse>(MapToResponse(saved!), Messages.FinancialIqResultCalculated);
    }

    // --- Core scoring logic ---
    // returns the breakdown as JSON text because that is how it is stored (nvarchar(max)); the API turns it into an object
    internal static (int score, string segment, string factorBreakdown) CalculateScore(CalculateRequest r)
    {
        // factor name -> points earned
        var factorScores = new Dictionary<string, decimal>();

        // prevents duplicate warnings if multiple thresholds trigger the same message
        var warnings = new HashSet<string>();

        // 0) Extreme amounts (see ScoringRules)
        // what the user owns minus what they owe; investments count in full here (they can repay the debt over time)
        var netDebt = r.TotalDebt - r.CashReserve - r.InvestmentAmount;
        //example lets say total debt is 150,000,000, cash 0 and investments 20,000,000 -> net debt 130,000,000
        //example lets say total debt is 1,000,000, cash 2,000,000 and investments 9,000,000 -> net debt -10,000,000 (net worth 10,000,000)

        // how many years of gross income the net debt equals (0 when the assets cover the debt)
        // with no income a net debt can never be repaid from it: as many years as can be
        var netDebtYears = netDebt <= 0 ? 0m : r.MonthlyIncome > 0 ? netDebt / (r.MonthlyIncome * 12) : decimal.MaxValue;
        //example lets say net debt is 150,000,000 and monthly income is 2,000,000 -> 150,000,000 / 24,000,000 = 6.25 years

        var appliedRule = GetAppliedRule(r.MonthlyIncome, netDebt, netDebtYears);
        //example lets say monthly income is 1,000,000, no debt and no cash yet -> VERY_HIGH_INCOME, score 100
        //example lets say the net worth is 10,000,000 and the salary is 30,000 -> VERY_HIGH_WEALTH, score 100
        //example lets say net debt is 130,000,000 and monthly income is 40,000 -> EXTREME_DEBT, score 0

        // 1) Cash reserve months
        // the reserve is the cash plus half of the investments (ScoringRules.InvestmentReserveShare)
        var reserve = r.CashReserve + r.InvestmentAmount * ScoringRules.InvestmentReserveShare;
        //example lets say cash is 3000 and investments are 10000, then reserve = 3000 + 10000 * 0.5 = 8000

        // with zero monthly expenses any positive reserve covers them indefinitely, so it counts as ample (6 months)
        var cashReserveMonths = r.MonthlyExpenses > 0
            ? reserve / r.MonthlyExpenses
            : reserve > 0 ? 6m : 0m;
        //cashReserveMonths is calculated by dividing the reserve by monthly expenses
        //example lets say the reserve is 6000 and monthly expenses is 2000, then cashReserveMonths = 6000 / 2000 = 3 .meaning the user has 3 months of reserve

        // points from the scale in ScoringRules: >= 6 months 25, >= 3 months 15, >= 1 month 8, otherwise 0
        //example lets say cashReserveMonths is 4.2 -> the first step reached is ">= 3", so 15 points
        Score("CashReserveMonths", ScoringRules.CashReserveMonths, cashReserveMonths, factorScores, warnings);

        // 2) Debt-to-income ratio
        // no income: an installment is the worst case, none the best (the same for the two ratios below)
        var debtRatio = r.MonthlyIncome > 0 ? r.MonthlyDebtPayment / r.MonthlyIncome : r.MonthlyDebtPayment > 0 ? decimal.MaxValue : 0m;
        //debtRatio is calculated by dividing the monthly debt payment by monthly income
        //example lets say monthly debt payment is 500 and monthly income is 5000, then debtRatio = 500 / 5000 = 0.1 .meaning the user has a debt-to-income ratio of 10%

        // <= 10% 25, <= 20% 15, <= 36% 8, otherwise 0 (and the "High debt burden" warning above 36%)
        var paymentPoints = ScoringRules.InstallmentToIncome.Points(debtRatio);
        AddWarning(ScoringRules.InstallmentToIncome, debtRatio, warnings);

        // the installment alone hides a large debt with a small or long-term payment, so the size of the
        // net debt compared with a year of income is scored too, and the factor takes the worse of the two
        // <= 0.5 years 25, <= 1 year 15, <= 3 years 8, otherwise 0 (and "High total debt" above 3 years)
        var debtLoadPoints = ScoringRules.NetDebtYearsOfIncome.Points(netDebtYears);
        AddWarning(ScoringRules.NetDebtYearsOfIncome, netDebtYears, warnings);
        //example lets say the installment is 5% of income (25 points) but the net debt is 6.25 years of income (0 points) -> factor = 0

        factorScores["DebtToIncomeRatio"] = Math.Min(paymentPoints, debtLoadPoints);

        // 3) Savings rate
        // no income: nothing can be saved, the factor gives 0 (someone with no income, no debt and no assets is LOW, not MEDIUM)
        var savingsRate = r.MonthlyIncome > 0 ? (r.MonthlyIncome - r.MonthlyExpenses - r.MonthlyDebtPayment) / r.MonthlyIncome : -1m;
        //savingsRate is calculated by subtracting monthly expenses and debt payment from monthly income, then dividing by monthly income
        //example lets say monthly income is 5000, monthly expenses is 2000, and monthly debt payment is 500,
        // then savingsRate = (5000 - 2000 - 500) / 5000 = 2500 / 5000 = 0.5 .meaning the user has a savings rate of 50%

        // >= 20% 25, >= 10% 15, >= 0 8, negative 0 (and the "Negative savings rate" warning)
        Score("SavingsRate", ScoringRules.SavingsRate, savingsRate, factorScores, warnings);

        // 4) Expense ratio
        var expenseRatio = r.MonthlyIncome > 0 ? r.MonthlyExpenses / r.MonthlyIncome : r.MonthlyExpenses > 0 ? decimal.MaxValue : 1m;
        //expenseRatio is calculated by dividing monthly expenses by monthly income
        //example lets say monthly expenses is 2000 and monthly income is 5000, then expenseRatio = 2000 / 5000 = 0.4 .meaning the user has an expense ratio of 40%

        // <= 40% 15, <= 60% 9, <= 80% 5, otherwise 0 (and "Overspending relative to income" above 80%)
        Score("ExpenseRatio", ScoringRules.ExpenseRatio, expenseRatio, factorScores, warnings);

        // 5) Impatience
        // self-reported 1-5, present bias: preferring a small reward now over a bigger one later
        // level 1 -> 10, 2 -> 8, 3 -> 5, 4 -> 2, 5 -> 0 (and "High impatience" from level 4)
        Score("Impatience", ScoringRules.Impatience, r.ImpatienceLevel, factorScores, warnings);

        // the rule replaces the factor points, so the bars in the apps still add up to the score
        if (appliedRule is ScoringRules.VeryHighIncomeRule or ScoringRules.VeryHighWealthRule)
        {
            foreach (var (factor, max) in FactorMaximums) factorScores[factor] = max;
            // the ratio warnings (e.g. "Low cash reserve") don't apply: this income or wealth covers them
            warnings.Clear();
        }
        else if (appliedRule == ScoringRules.ExtremeDebtRule)
        {
            foreach (var factor in FactorMaximums.Keys) factorScores[factor] = 0;
            warnings.Add(ScoringRules.ExtremeDebtWarning);
        }

        var totalScore = (int)factorScores.Values.Sum();

        // v2.1: the way to the special rules is continuous (see ScoringRules); the factors stay as they are, the change is reported
        object? adjustment = null;
        if (appliedRule is null)
        {
            var (adjusted, rule) = Adjust(totalScore, r, netDebt, netDebtYears);
            if (adjusted != totalScore)
            {
                adjustment = new { rule, fromFactors = totalScore, score = adjusted };
                totalScore = adjusted;
            }
        }

        var segment = totalScore switch
        {
            >= ScoringRules.HighSegmentMinScore => "HIGH",
            >= ScoringRules.MediumSegmentMinScore => "MEDIUM",
            _ => "LOW"
        };
        // bundle scores + warnings into one JSON document so the AI/RAG service can explain "why" this score, not just "what"
        // appliedRule is null when the 5 factors decided the score; version tells results of older rules apart
        // adjustment (v2.1, optional): when a floor or cap changed the sum of the factors; null otherwise
        var breakdown = new { version = ScoringRules.ScoringVersion, factors = factorScores, warnings, appliedRule, adjustment };
        var factorBreakdownJson = JsonSerializer.Serialize(breakdown);
        return (totalScore, segment, factorBreakdownJson);
    }

    // floors raise the score of the very wealthy or the very high earner who is just below a rule; the cap lowers the score of
    // a net debt that income cannot carry. They exclude each other: a floor needs little or no net debt, the cap a large one.
    // example lets say net worth is 9,900,000 and the outgoings are 19,000 a month -> 9,900,000 / (25 x 228,000) = 1.7 -> floor 100
    // example lets say income is 999,999 with no debt -> floor 99
    // example lets say income is 40,000 and net debt 99,000,000 -> 206 years -> cap 0; net debt 2,000,000 -> 4.2 years -> cap 37
    internal static (int score, string? rule) Adjust(int factors, CalculateRequest r, decimal netDebt, decimal netDebtYears)
    {
        int score = factors;
        string? rule = null;
        var outgoings = 12 * (r.MonthlyExpenses + r.MonthlyDebtPayment);
        if (netDebt < 0 && outgoings > 0)
        {
            var floor = (int)Math.Min(100m, 100m * -netDebt / (ScoringRules.WealthYearsForFullScore * outgoings));
            if (floor > score) (score, rule) = (floor, ScoringRules.WealthFloorRule);
        }
        if (r.MonthlyIncome > 0 && netDebtYears <= ScoringRules.VeryHighIncomeMaxNetDebtYears)
        {
            var floor = (int)Math.Min(100m, 100m * r.MonthlyIncome / ScoringRules.VeryHighMonthlyIncome);
            if (floor > score) (score, rule) = (floor, ScoringRules.IncomeFloorRule);
        }
        if (netDebtYears > ScoringRules.HighNetDebtYears)
        {
            var cap = netDebtYears == decimal.MaxValue ? 0
                : (int)Math.Max(0m, ScoringRules.DebtCapAtLimit - ScoringRules.DebtCapPerYear * (netDebtYears - ScoringRules.HighNetDebtYears));
            if (cap < score) (score, rule) = (cap, ScoringRules.DebtCapRule);
        }
        return (score, rule);
    }

    private static void Score(string factor, ScoreScale scale, decimal value, Dictionary<string, decimal> factorScores, HashSet<string> warnings)
    {
        factorScores[factor] = scale.Points(value);
        AddWarning(scale, value, warnings);
    }

    private static void AddWarning(ScoreScale scale, decimal value, HashSet<string> warnings)
    {
        if (scale.Warning is { } warning && warning.Fires(value)) warnings.Add(warning.Text);
    }

    // very high income -> 100 only while the net debt is small (at most 1 year of income);
    // very high net worth -> 100 whatever the income;
    // extreme net debt -> 0 only for incomes below the very-high line. Anything else: the factors decide.
    // example: income 2,000,000 with 150,000,000 net debt (6.25 years) -> no rule, the debt factor gives 0
    // example: income 1,000,000 with 90,000,000 net debt (7.5 years) -> no rule, NOT an automatic 100
    // example: income 30,000 with 10,000,000 net worth -> VERY_HIGH_WEALTH
    internal static string? GetAppliedRule(decimal monthlyIncome, decimal netDebt, decimal netDebtYears)
    {
        var veryHighIncome = monthlyIncome >= ScoringRules.VeryHighMonthlyIncome;

        if (veryHighIncome && netDebtYears <= ScoringRules.VeryHighIncomeMaxNetDebtYears) return ScoringRules.VeryHighIncomeRule;
        // net worth is the negative of the net debt
        if (-netDebt >= ScoringRules.VeryHighNetWorth) return ScoringRules.VeryHighWealthRule;
        if (!veryHighIncome && netDebt >= ScoringRules.ExtremeNetDebt) return ScoringRules.ExtremeDebtRule;
        return null;
    }

    internal static FinancialIqResultResponse MapToResponse(FinancialIqResult entity) => new()
    {
        Id = entity.Id,
        UserId = entity.UserId,
        Score = entity.Score,
        Segment = entity.Segment,
        FactorBreakdown = FactorBreakdownJson.ToElement(entity.FactorBreakdown),
        CreatedAt = entity.CreatedAt,
        UpdatedAt = entity.UpdatedAt,
        ResultVersion = ResultVersion.FromRowVersion(entity.RowVersion)
    };
}
