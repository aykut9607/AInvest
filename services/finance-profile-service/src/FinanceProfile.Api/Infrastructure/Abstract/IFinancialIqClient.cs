using FinanceProfile.Api.Core.Utilities.Results;
using FinanceProfile.Api.DTOs;

namespace FinanceProfile.Api.Infrastructure.Abstract;
public interface IFinancialIqClient
{
    Task<IDataResult<FinancialIqCalculateResponse>> CalculateAsync(FinancialIqCalculateRequest request);
}