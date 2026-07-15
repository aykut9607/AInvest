using FinancialIQ.Api.Core.Utilities.Results;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Api.Application.Abstract;

public interface IFinancialIqResultService
{
    Task<IDataResult<FinancialIqResultResponse>> GetLatestAsync(string userId);
    Task<IDataResult<FinancialIqResultResponse>> CalculateAsync(CalculateRequest request);
}