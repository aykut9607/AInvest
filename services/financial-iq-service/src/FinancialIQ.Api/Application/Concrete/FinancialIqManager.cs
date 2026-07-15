using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Core.Utilities.Results;
using IResult = FinancialIQ.Api.Core.Utilities.Results.IResult;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Infrastructure.Abstract;

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

        var (score, segment) = CalculateScore(request);

        var entity = new FinancialIqResult
        {
            UserId = request.UserId,
            Score = score,
            Segment = segment,
            UpdatedAt = DateTime.UtcNow
        };

        await _dal.UpsertAsync(entity);

        var saved = await _dal.GetAsync(x => x.UserId == request.UserId);
        return new SuccessDataResult<FinancialIqResultResponse>(MapToResponse(saved!), Messages.FinancialIqResultCalculated);
    }

    // --- Core scoring logic ---
    private static (int score, string segment) CalculateScore(CalculateRequest r)
    {
        // factor name -> points earned
        var factorScores = new Dictionary<string, decimal>();
        // prevents duplicate warnings if multiple thresholds trigger the same message
        var warnings = new HashSet<string>();

        // 1) Cash reserve months
        var cashReserveMonths = r.MonthlyExpenses > 0 ? r.CashReserve / r.MonthlyExpenses : 0;
        factorScores["CashReserveMonths"] = cashReserveMonths switch
        {
            >= 6 => 25,
            >= 3 => 15,
            >= 1 => 8,
            _ => 0
        };
        if (cashReserveMonths < 3) warnings.Add("Low cash reserve");

        // 2) Debt-to-income ratio
        var debtRatio = r.MonthlyDebtPayment / r.MonthlyIncome;
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
            >= 80 => "STRONG",
            >= 55 => "BALANCED",
            >= 30 => "NEEDS_IMPROVEMENT",
            _ => "HIGH_RISK"
        };

        return (totalScore, segment);
    }

    private static FinancialIqResultResponse MapToResponse(FinancialIqResult entity) => new()
    {
        Id = entity.Id,
        UserId = entity.UserId,
        Score = entity.Score,
        Segment = entity.Segment,
        CreatedAt = entity.CreatedAt,
        UpdatedAt = entity.UpdatedAt
    };
}