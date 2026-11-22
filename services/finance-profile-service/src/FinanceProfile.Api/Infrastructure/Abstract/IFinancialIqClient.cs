using System.Text.Json;
using FinanceProfile.Api.Application.Results;
using FinanceProfile.Api.DTOs;

namespace FinanceProfile.Api.Infrastructure.Abstract;
public interface IFinancialIqClient
{
    Task<IDataResult<FinancialIqCalculateResponse>> CalculateAsync(FinancialIqCalculateRequest request);

    // the payoff schedule is IQ's answer passed on as-is (IQ owns its shape: months, totals, schedule rows)
    Task<IDataResult<JsonElement?>> GetDebtPayoffAsync(FinancialIqDebtPayoffRequest request);
}
