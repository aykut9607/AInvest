using FinancialIQ.Api.Application.Results;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Api.Application.Abstract;

// CQRS-lite, read side: never changes data and returns DTOs straight from the database
// (dbo.usp_GetLatestIqResult, dbo.fn_IqTrend), without loading tracked entities first.
// "lite" = same database and same model for both sides; only the code paths are separated.
public interface IFinancialIqQueryService
{
    Task<IDataResult<FinancialIqResultResponse>> GetLatestAsync(string userId);

    Task<IDataResult<List<IqTrendPointResponse>>> GetHistoryAsync(string userId, int take);
}
