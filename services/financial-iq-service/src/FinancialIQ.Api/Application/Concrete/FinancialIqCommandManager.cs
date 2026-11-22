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
    internal static readonly IReadOnlyDictionary<string, decimal> FactorMaximums = new Dictionary<string, decimal>
    {
        ["CashReserveMonths"] = 25,
        ["DebtToIncomeRatio"] = 25,
        ["SavingsRate"] = 25,
        ["ExpenseRatio"] = 15,
        ["Impatience"] = 10
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

        if (request.MonthlyIncome <= 0)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidMonthlyIncome);

        if (request.MonthlyExpenses < 0 || request.MonthlyDebtPayment < 0 || request.CashReserve < 0 || request.TotalDebt < 0 || request.InvestmentAmount < 0)
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
        var netDebtYears = netDebt > 0 ? netDebt / (r.MonthlyIncome * 12) : 0m;
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

        factorScores["CashReserveMonths"] = cashReserveMonths switch
        //switch expression used to determine the score based on cash reserve months
        {
            >= 6 => 25,
            //if cash reserve months is greater than or equal to 6, then the score is 25.

            >= 3 => 15,
            >= 1 => 8,
            _ => 0
        };
        if (cashReserveMonths < 3) warnings.Add("Low cash reserve");

        // 2) Debt-to-income ratio
        var debtRatio = r.MonthlyDebtPayment / r.MonthlyIncome;
        //debtRatio is calculated by dividing the monthly debt payment by monthly income
        //example lets say monthly debt payment is 500 and monthly income is 5000, then debtRatio = 500 / 5000 = 0.1 .meaning the user has a debt-to-income ratio of 10%

        var paymentPoints = debtRatio switch
        {
            <= 0.10m => 25,
            <= 0.20m => 15,
            <= 0.36m => 8,
            _ => 0
        };
        if (debtRatio > 0.36m) warnings.Add("High debt burden");

        // the installment alone hides a large debt with a small or long-term payment, so the size of the
        // net debt compared with a year of income is scored too, and the factor takes the worse of the two
        var debtLoadPoints = netDebtYears switch
        {
            <= 0.5m => 25,
            <= 1m => 15,
            <= ScoringRules.HighNetDebtYears => 8,
            _ => 0
        };
        if (netDebtYears > ScoringRules.HighNetDebtYears) warnings.Add(ScoringRules.HighTotalDebtWarning);
        //example lets say the installment is 5% of income (25 points) but the net debt is 6.25 years of income (0 points) -> factor = 0

        factorScores["DebtToIncomeRatio"] = Math.Min(paymentPoints, debtLoadPoints);

        // 3) Savings rate
        var savingsRate = (r.MonthlyIncome - r.MonthlyExpenses - r.MonthlyDebtPayment) / r.MonthlyIncome;
        //savingsRate is calculated by subtracting monthly expenses and debt payment from monthly income, then dividing by monthly income
        //example lets say monthly income is 5000, monthly expenses is 2000, and monthly debt payment is 500,
        // then savingsRate = (5000 - 2000 - 500) / 5000 = 2500 / 5000 = 0.5 .meaning the user has a savings rate of 50%

        factorScores["SavingsRate"] = savingsRate switch
        {
            >= 0.20m => 25,
            >= 0.10m => 15,
            >= 0m => 8,
            _ => 0
        };
        if (savingsRate < 0) warnings.Add("Negative savings rate");

        // 4) Expense ratio
        var expenseRatio = r.MonthlyExpenses / r.MonthlyIncome;
        //expenseRatio is calculated by dividing monthly expenses by monthly income
        //example lets say monthly expenses is 2000 and monthly income is 5000, then expenseRatio = 2000 / 5000 = 0.4 .meaning the user has an expense ratio of 40%

        factorScores["ExpenseRatio"] = expenseRatio switch
        {
            <= 0.40m => 15,
            <= 0.60m => 9,
            <= 0.80m => 5,
            _ => 0
        };
        if (expenseRatio > 0.80m) warnings.Add("Overspending relative to income");

        // 5) Impatience
        // self-reported 1-5, present bias: preferring a small reward now over a bigger one later
        factorScores["Impatience"] = r.ImpatienceLevel switch
        {
            1 => 10,
            2 => 8,
            3 => 5,
            4 => 2,
            _ => 0
        };
        if (r.ImpatienceLevel >= 4) warnings.Add("High impatience");

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

        var segment = totalScore switch
        {
            >= 71 => "HIGH",
            >= 41 => "MEDIUM",
            _ => "LOW"
        };
        // bundle scores + warnings into one JSON document so the AI/RAG service can explain "why" this score, not just "what"
        // appliedRule is null when the 5 factors decided the score; version tells results of older rules apart
        var breakdown = new { version = ScoringRules.ScoringVersion, factors = factorScores, warnings, appliedRule };
        var factorBreakdownJson = JsonSerializer.Serialize(breakdown);
        return (totalScore, segment, factorBreakdownJson);
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
