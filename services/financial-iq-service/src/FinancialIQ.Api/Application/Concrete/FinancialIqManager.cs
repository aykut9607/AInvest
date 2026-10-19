using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Application.Results;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Infrastructure.Abstract;
using System.Text.Json;

namespace FinancialIQ.Api.Application.Concrete;

public class FinancialIqManager : IFinancialIqResultService
{
    private readonly IFinancialIqResultDal _dal;

    // ordered low -> high, the index is used as the risk "level" when comparing stated vs behavioral risk
    private static readonly string[] RiskLevels = { "LOW", "MEDIUM", "HIGH" };

    public FinancialIqManager(IFinancialIqResultDal dal)
    {
        _dal = dal;
    }

    public async Task<IDataResult<FinancialIqResultResponse>> GetLatestAsync(string userId)
    {
        var result = await _dal.GetAsync(x => x.UserId == userId);
        if (result == null)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.FinancialIqResultNotFound);

        return new SuccessDataResult<FinancialIqResultResponse>(MapToResponse(result), Messages.FinancialIqResultRetrieved);
    }

    public async Task<IDataResult<FinancialIqResultResponse>> CalculateAsync(CalculateRequest request)
    {
        if (request.MonthlyIncome <= 0)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidMonthlyIncome);

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

        await _dal.UpsertAsync(entity);

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

        // 1) Cash reserve months
        // with zero monthly expenses any positive reserve covers them indefinitely, so it counts as ample (6 months)
        var cashReserveMonths = r.MonthlyExpenses > 0
            ? r.CashReserve / r.MonthlyExpenses
            : r.CashReserve > 0 ? 6m : 0m;
        //cashReserveMonths is calculated by dividing the cash reserve by monthly expenses
        //example lets say cash reserve is 6000 and monthly expenses is 2000, then cashReserveMonths = 6000 / 2000 = 3 .meaning the user has 3 months of cash reserve

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

        factorScores["DebtToIncomeRatio"] = debtRatio switch
        {
            <= 0.10m => 20,
            <= 0.20m => 12,
            <= 0.36m => 6,
            _ => 0
        };
        if (debtRatio > 0.36m) warnings.Add("High debt burden");

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
        var behavioralRisk = GetBehavioralRiskCapacity(cashReserveMonths, debtRatio, savingsRate);
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

        var totalScore = (int)factorScores.Values.Sum();

        var segment = totalScore switch
        {
            >= 71 => "HIGH",
            >= 41 => "MEDIUM",
            _ => "LOW"
        };
        // bundle scores + warnings into one JSON string so the AI/RAG service can explain "why" this score, not just "what"
        var breakdown = new { factors = factorScores, warnings, riskProfile };
        var factorBreakdownJson = JsonSerializer.Serialize(breakdown);
        return (totalScore, segment, factorBreakdownJson);
    }

    // thresholds reuse the warning lines of factors 1-3, so LOW means at least one of those warnings fired
    internal static string GetBehavioralRiskCapacity(decimal cashReserveMonths, decimal debtRatio, decimal savingsRate)
    {
        if (cashReserveMonths < 3 || debtRatio > 0.36m || savingsRate < 0)
            return "LOW";

        if (cashReserveMonths >= 6 && debtRatio <= 0.20m && savingsRate >= 0.10m)
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