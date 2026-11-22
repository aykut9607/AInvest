using FinanceProfile.Api.Application.Results;
using IResult = FinanceProfile.Api.Application.Results.IResult;
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
    // month-by-month payoff of the profile's total debt with its monthly installment (computed by IQ)
    Task<IDataResult<System.Text.Json.JsonElement?>> GetDebtPayoffAsync(string userId, decimal? monthlyInterestRate);
}