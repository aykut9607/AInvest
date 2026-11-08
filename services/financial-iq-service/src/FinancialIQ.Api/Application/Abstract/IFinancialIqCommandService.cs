using FinancialIQ.Api.Application.Results;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Api.Application.Abstract;

// CQRS-lite, write side: everything that changes data. Reads live in IFinancialIqQueryService.
public interface IFinancialIqCommandService
{
    // validates the input, calculates the score and saves it (latest result + a history row)
    Task<IDataResult<FinancialIqResultResponse>> CalculateAsync(CalculateRequest request);
}
