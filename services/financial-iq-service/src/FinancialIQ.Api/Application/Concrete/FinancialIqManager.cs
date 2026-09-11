using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Core.Utilities.Results;
using IResult = FinancialIQ.Api.Core.Utilities.Results.IResult;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Infrastructure.Abstract;
using System.Text.Json;

namespace FinancialIQ.Api.Application.Concrete;

public class FinancialIqManager : IFinancialIqResultService
{
    private readonly IFinancialIqResultDal _dal;

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
        // factor name -> points earned (Dictionary usage required by the posting's "data structures" criterion)
        var factorScores = new Dictionary<string, decimal>();

        // prevents duplicate warnings if multiple thresholds trigger the same message
        var warnings = new HashSet<string>();

        // 1) Cash reserve months
        var cashReserveMonths = r.MonthlyExpenses > 0 ? r.CashReserve / r.MonthlyExpenses : 0;
        //cashReserveMonths is calculated by dividing the cash reserve by monthly expenses
        //example lets say cash reserve is 6000 and monthly expenses is 2000, then cashReserveMonths = 6000 / 2000 = 3 .meaning the user has 3 months of cash reserve

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

        factorScores["DebtToIncomeRatio"] = debtRatio switch
        {
            <= 0.10m => 25,
            <= 0.20m => 15,
            <= 0.36m => 8,
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
            <= 0.40m => 25,
            <= 0.60m => 15,
            <= 0.80m => 8,
            _ => 0
        };
        if (expenseRatio > 0.80m) warnings.Add("Overspending relative to income");

        var totalScore = (int)factorScores.Values.Sum();

        var segment = totalScore switch
        {
            >= 71 => "HIGH",
            >= 41 => "MEDIUM",
            _ => "LOW"
        };
        // bundle scores + warnings into one JSON string so the AI/RAG service can explain "why" this score, not just "what"
        var breakdown = new { factors = factorScores, warnings };
        var factorBreakdownJson = JsonSerializer.Serialize(breakdown);
        return (totalScore, segment, factorBreakdownJson);
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