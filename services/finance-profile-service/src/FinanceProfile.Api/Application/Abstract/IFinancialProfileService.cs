using FinanceProfile.Api.Core.Utilities.Results;
using IResult = FinanceProfile.Api.Core.Utilities.Results.IResult;
using FinanceProfile.Api.Domain.Entities;
using FinanceProfile.Api.DTOs;

namespace FinanceProfile.Api.Application.Abstract;

public interface IFinancialProfileService
{
    Task<IDataResult<List<FinancialProfileResponse>>> GetAllAsync();
    Task<IDataResult<FinancialProfileResponse>> GetByUserIdAsync(string userId);
    Task<IResult> UpsertAsync(string id, UpsertFinancialProfileRequest request);
    Task<IResult>DeleteAsync(string id);
    Task<IDataResult<FinancialIqCalculateResponse>> CalculateIqAsync(string userId);
}