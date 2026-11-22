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

    // ordered low -> high, the index is used as the risk "level" when comparing stated vs behavioral risk
    private static readonly string[] RiskLevels = { "LOW", "MEDIUM", "HIGH" };

    // the most each factor can give (sum = 100); used when a rule in ScoringRules decides the score
    private static readonly Dictionary<string, decimal> FactorMaximums = new()
    {
        ["CashReserveMonths"] = 20,
        ["DebtToIncomeRatio"] = 20,
        ["SavingsRate"] = 20,
        ["ExpenseRatio"] = 15,
        ["RiskAlignment"] = 15,
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

        if (!RiskLevels.Contains(request.RiskPreference))
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidRiskPreference);

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
    internal static (int score, string segment, string factorBreakdown) CalculateScore(CalculateRequest r)
    {
        // factor name -> points earned
        var factorScores = new Dictionary<string, decimal>();

        // prevents duplicate warnings if multiple thresholds trigger the same message
        var warnings = new HashSet<string>();

        // 0) Extreme amounts (see ScoringRules): checked first because they also set the risk capacity in factor 5
        // what the user owns minus what they owe; investments count in full here (they can repay the debt over time)
        var netDebt = r.TotalDebt - r.CashReserve - r.InvestmentAmount;
        //example lets say total debt is 150,000,000, cash 0 and investments 20,000,000 -> net debt 130,000,000

        // how many years of gross income the net debt equals (0 when the assets cover the debt)
        var netDebtYears = netDebt > 0 ? netDebt / (r.MonthlyIncome * 12) : 0m;
        //example lets say net debt is 150,000,000 and monthly income is 2,000,000 -> 150,000,000 / 24,000,000 = 6.25 years

        var appliedRule = GetAppliedRule(r.MonthlyIncome, netDebt, netDebtYears);
        //example lets say monthly income is 1,000,000, no debt and no cash yet -> VERY_HIGH_INCOME, score 100
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
            >= 6 => 20,
            //if cash reserve months is greater than or equal to 6, then the score is 20.

            >= 3 => 12,
            >= 1 => 6,
            _ => 0
        };
        if (cashReserveMonths < 3) warnings.Add("Low cash reserve");

        // 2) Debt-to-income ratio
        var debtRatio = r.MonthlyDebtPayment / r.MonthlyIncome;
        //debtRatio is calculated by dividing the monthly debt payment by monthly income
        //example lets say monthly debt payment is 500 and monthly income is 5000, then debtRatio = 500 / 5000 = 0.1 .meaning the user has a debt-to-income ratio of 10%

        var paymentPoints = debtRatio switch
        {
            <= 0.10m => 20,
            <= 0.20m => 12,
            <= 0.36m => 6,
            _ => 0
        };
        if (debtRatio > 0.36m) warnings.Add("High debt burden");

        // the installment alone hides a large debt with a small or long-term payment, so the size of the
        // net debt compared with a year of income is scored too, and the factor takes the worse of the two
        var debtLoadPoints = netDebtYears switch
        {
            <= 0.5m => 20,
            <= 1m => 12,
            <= ScoringRules.HighNetDebtYears => 6,
            _ => 0
        };
        if (netDebtYears > ScoringRules.HighNetDebtYears) warnings.Add(ScoringRules.HighTotalDebtWarning);
        //example lets say the installment is 5% of income (20 points) but the net debt is 6.25 years of income (0 points) -> factor = 0

        factorScores["DebtToIncomeRatio"] = Math.Min(paymentPoints, debtLoadPoints);

        // 3) Savings rate
        var savingsRate = (r.MonthlyIncome - r.MonthlyExpenses - r.MonthlyDebtPayment) / r.MonthlyIncome;
        //savingsRate is calculated by subtracting monthly expenses and debt payment from monthly income, then dividing by monthly income
        //example lets say monthly income is 5000, monthly expenses is 2000, and monthly debt payment is 500, 
        // then savingsRate = (5000 - 2000 - 500) / 5000 = 2500 / 5000 = 0.5 .meaning the user has a savings rate of 50%

        factorScores["SavingsRate"] = savingsRate switch
        {
            >= 0.20m => 20,
            >= 0.10m => 12,
            >= 0m => 6,
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

        // 5) Risk alignment
        // compares the self-reported risk preference with the risk the user's numbers can actually carry
        // a very high income can carry high risk even before a reserve exists; an extreme debt cannot carry any
        var behavioralRisk = appliedRule switch
        {
            ScoringRules.VeryHighIncomeRule => "HIGH",
            ScoringRules.ExtremeDebtRule => "LOW",
            _ => GetBehavioralRiskCapacity(cashReserveMonths, debtRatio, savingsRate, netDebtYears)
        };
        var levelGap = Array.IndexOf(RiskLevels, r.RiskPreference) - Array.IndexOf(RiskLevels, behavioralRisk);
        //levelGap > 0 means the user claims more risk than their finances allow
        //example lets say stated is HIGH (2) and behavioral is LOW (0), then levelGap = 2 .meaning two levels overstated

        factorScores["RiskAlignment"] = Math.Abs(levelGap) switch
        {
            0 => 15,
            1 => 8,
            _ => 0
        };
        if (levelGap > 0) warnings.Add("Stated risk preference exceeds financial capacity");

        // the inconsistency flag the AI coach reads to say "you say HIGH, your numbers say LOW"
        var riskProfile = new
        {
            stated = r.RiskPreference,
            behavioral = behavioralRisk,
            inconsistent = levelGap != 0,
            direction = levelGap switch
            {
                > 0 => "OVERSTATED",
                < 0 => "UNDERSTATED",
                _ => "ALIGNED"
            }
        };

        // 6) Impatience
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
        if (appliedRule == ScoringRules.VeryHighIncomeRule)
        {
            foreach (var (factor, max) in FactorMaximums) factorScores[factor] = max;
            // the ratio warnings (e.g. "Low cash reserve") don't apply: at this income they fix themselves quickly
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
        // bundle scores + warnings into one JSON string so the AI/RAG service can explain "why" this score, not just "what"
        // appliedRule is null when the 6 factors decided the score
        var breakdown = new { factors = factorScores, warnings, riskProfile, appliedRule };
        var factorBreakdownJson = JsonSerializer.Serialize(breakdown);
        return (totalScore, segment, factorBreakdownJson);
    }

    // very high income -> 100 only while the net debt is small (at most 1 year of income);
    // extreme net debt -> 0 only for incomes below the very-high line. Anything else: the factors decide.
    // example: income 2,000,000 with 150,000,000 net debt (6.25 years) -> no rule, the debt factor gives 0
    // example: income 1,000,000 with 90,000,000 net debt (7.5 years) -> no rule, NOT an automatic 100
    internal static string? GetAppliedRule(decimal monthlyIncome, decimal netDebt, decimal netDebtYears)
    {
        var veryHighIncome = monthlyIncome >= ScoringRules.VeryHighMonthlyIncome;

        if (veryHighIncome && netDebtYears <= ScoringRules.VeryHighIncomeMaxNetDebtYears) return ScoringRules.VeryHighIncomeRule;
        if (!veryHighIncome && netDebt >= ScoringRules.ExtremeNetDebt) return ScoringRules.ExtremeDebtRule;
        return null;
    }

    // thresholds reuse the warning lines of factors 1-3 and the net-debt load, so LOW means at least one of those warnings fired
    internal static string GetBehavioralRiskCapacity(decimal cashReserveMonths, decimal debtRatio, decimal savingsRate, decimal netDebtYears = 0)
    {
        if (cashReserveMonths < 3 || debtRatio > 0.36m || savingsRate < 0 || netDebtYears > ScoringRules.HighNetDebtYears)
            return "LOW";

        if (cashReserveMonths >= 6 && debtRatio <= 0.20m && savingsRate >= 0.10m && netDebtYears <= 1m)
            return "HIGH";

        return "MEDIUM";
    }

    private static FinancialIqResultResponse MapToResponse(FinancialIqResult entity) => new()
{
    Id = entity.Id,
    UserId = entity.UserId,
    Score = entity.Score,
    Segment = entity.Segment,
    FactorBreakdown = entity.FactorBreakdown,
    CreatedAt = entity.CreatedAt,
    UpdatedAt = entity.UpdatedAt
};
}