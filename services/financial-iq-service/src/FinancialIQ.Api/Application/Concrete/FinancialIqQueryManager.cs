using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Application.Results;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Infrastructure.Abstract;

namespace FinancialIQ.Api.Application.Concrete;

// CQRS-lite read side: only input checks and turning "nothing found" into a message; it never writes
public class FinancialIqQueryManager : IFinancialIqQueryService
{
    private readonly IFinancialIqReadDal _readDal;

    // upper limit for one history request, so a caller cannot ask for an unbounded result set
    private const int MaxHistoryTake = 100;

    public FinancialIqQueryManager(IFinancialIqReadDal readDal)
    {
        _readDal = readDal;
    }

    public async Task<IDataResult<FinancialIqResultResponse>> GetLatestAsync(string userId)
    {
        if (!IsValidUserId(userId))
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidUserId);

        var latest = await _readDal.GetLatestAsync(userId);
        if (latest == null)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.FinancialIqResultNotFound);

        return new SuccessDataResult<FinancialIqResultResponse>(latest, Messages.FinancialIqResultRetrieved);
    }

    public async Task<IDataResult<List<IqTrendPointResponse>>> GetHistoryAsync(string userId, int take)
    {
        if (!IsValidUserId(userId))
            return new ErrorDataResult<List<IqTrendPointResponse>>(Messages.InvalidUserId);

        if (take < 1 || take > MaxHistoryTake)
            return new ErrorDataResult<List<IqTrendPointResponse>>(Messages.InvalidHistoryTake);

        var points = await _readDal.GetTrendAsync(userId, take);
        if (points.Count == 0)
            return new ErrorDataResult<List<IqTrendPointResponse>>(Messages.FinancialIqHistoryNotFound);

        return new SuccessDataResult<List<IqTrendPointResponse>>(points, Messages.FinancialIqHistoryRetrieved);
    }

    public async Task<IDataResult<DebtPayoffResponse>> GetDebtPayoffAsync(DebtPayoffRequest request)
    {
        if (request.TotalDebt < 0 || request.MonthlyPayment < 0)
            return new ErrorDataResult<DebtPayoffResponse>(Messages.NegativeAmountNotAllowed);

        // same technical limit as Finance's numeric(18,2) columns; a larger value would overflow the SQL parameter
        if (request.TotalDebt > MaxAmount || request.MonthlyPayment > MaxAmount)
            return new ErrorDataResult<DebtPayoffResponse>(Messages.AmountTooLarge);

        var rate = request.MonthlyInterestRate ?? DebtPayoffRules.DefaultMonthlyInterestRate;
        if (rate < 0 || rate > DebtPayoffRules.MaxMonthlyInterestRate)
            return new ErrorDataResult<DebtPayoffResponse>(Messages.InvalidMonthlyInterestRate);

        var response = new DebtPayoffResponse
        {
            TotalDebt = request.TotalDebt,
            MonthlyPayment = request.MonthlyPayment,
            MonthlyInterestRate = rate
        };

        // the answers that need no schedule are given here, without asking the database
        if (request.TotalDebt == 0)
        {
            response.PaidOff = true;
            response.Months = 0;
            return new SuccessDataResult<DebtPayoffResponse>(response, Messages.NoDebtToPayOff);
        }

        // if the installment is not more than the first month's interest the balance never goes down: the schedule
        // would only run to the 600-month limit. Same rounding as the SQL function (to kuruş)
        var firstMonthInterest = Math.Round(request.TotalDebt * rate, 2);
        if (request.MonthlyPayment <= firstMonthInterest)
        {
            response.PaidOff = false;
            return new SuccessDataResult<DebtPayoffResponse>(response, Messages.PaymentDoesNotCoverInterest);
        }

        var schedule = await _readDal.GetDebtPayoffScheduleAsync(request.TotalDebt, request.MonthlyPayment, rate, DebtPayoffRules.MaxMonths);

        response.Schedule = schedule;
        response.TotalInterest = schedule.Sum(m => m.Interest);
        response.TotalPaid = schedule.Sum(m => m.Payment);
        response.PaidOff = schedule.Count > 0 && schedule[^1].ClosingBalance == 0;
        response.Months = response.PaidOff ? schedule.Count : null;

        return new SuccessDataResult<DebtPayoffResponse>(response,
            response.PaidOff ? Messages.DebtPayoffCalculated : Messages.DebtNotPaidOffWithinLimit);
    }

    public async Task<IDataResult<List<ScoringRulesResponse>>> GetScoringRulesAsync()
    {
        var versions = await _readDal.GetScoringRulesAsync();
        return new SuccessDataResult<List<ScoringRulesResponse>>(versions, Messages.ScoringRulesRetrieved);
    }

    public async Task<IDataResult<ScoringRulesResponse>> GetScoringRulesAsync(string version)
    {
        // "current" = whatever version is active; otherwise the exact version name (v1, v2, ...)
        var versions = await _readDal.GetScoringRulesAsync();
        var match = version.Equals("current", StringComparison.OrdinalIgnoreCase)
            ? versions.FirstOrDefault(v => v.IsActive)
            : versions.FirstOrDefault(v => v.Version.Equals(version, StringComparison.OrdinalIgnoreCase));

        return match == null
            ? new ErrorDataResult<ScoringRulesResponse>(Messages.ScoringVersionNotFound)
            : new SuccessDataResult<ScoringRulesResponse>(match, Messages.ScoringRulesRetrieved);
    }

    private const decimal MaxAmount = 999_999_999_999_999m;

    // same limit as the column (nvarchar(100)); checked before the database is asked
    private static bool IsValidUserId(string userId)
        => !string.IsNullOrWhiteSpace(userId) && userId.Length <= FinancialIqResult.UserIdMaxLength;
}
