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

    // same limit as the column (nvarchar(100)); checked before the database is asked
    private static bool IsValidUserId(string userId)
        => !string.IsNullOrWhiteSpace(userId) && userId.Length <= FinancialIqResult.UserIdMaxLength;
}
