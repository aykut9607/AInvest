using FinanceProfile.Api.Application.Abstract;
using FinanceProfile.Api.Application.Constants;
using FinanceProfile.Api.Core.Utilities.Results;
using IResult = FinanceProfile.Api.Core.Utilities.Results.IResult;
using FinanceProfile.Api.Domain.Entities;
using FinanceProfile.Api.Infrastructure.Abstract;
using FinanceProfile.Api.DTOs;
using FinanceProfile.Api.Infrastructure.External;

namespace FinanceProfile.Api.Application.Concrete;


public class FinancialProfileManager : IFinancialProfileService
{
        private readonly IFinancialProfileDal _financialProfileDal;
        private readonly IFinancialIqClient _financialIqClient;


    public FinancialProfileManager(IFinancialProfileDal financialProfileDal, IFinancialIqClient financialIqClient)
    {
        _financialProfileDal = financialProfileDal;
        _financialIqClient = financialIqClient;
    }

    public async Task<IDataResult<List<FinancialProfileResponse>>> GetAllAsync()
    {
       var financialProfiles = await _financialProfileDal.GetAllAsync();
       var response=financialProfiles.Select(MapToResponse).ToList();
        //In LINQ, Select means 'apply this function to every element in the list.
        return new SuccessDataResult<List<FinancialProfileResponse>>(response, Messages.FinancialProfileListed);
    }

    public async Task<IDataResult<FinancialProfileResponse>> GetByUserIdAsync(string userId)
    {
        var financialProfile=await _financialProfileDal.GetAsync(x => x.UserId == userId);
        if(financialProfile==null)
        {
            return new ErrorDataResult<FinancialProfileResponse>(Messages.FinancialProfileNotFound);
        }
        return new SuccessDataResult<FinancialProfileResponse>(MapToResponse(financialProfile), Messages.FinancialProfileRetrieved);
    }

   public async Task<IResult> UpsertAsync(string id, UpsertFinancialProfileRequest request)
    {
        if(request.MonthlyIncome <= 0)
         return new ErrorResult(Messages.InvalidMonthlyIncome);

        if (request.MonthlyExpenses < 0 || request.MonthlyDebtPayment < 0 || request.TotalDebt < 0 || request.CashReserve < 0 || request.InvestmentAmount < 0)
         return new ErrorResult(Messages.NegativeAmountNotAllowed);

        var allowedRisks = new[] { "LOW", "MEDIUM", "HIGH" };
        if (!allowedRisks.Contains(request.RiskPreference))
         return new ErrorResult(Messages.InvalidRiskPreference);
        
            var entity= MapToEntity(id, request);
            await _financialProfileDal.UpsertAsync(entity);
            return new SuccessResult(Messages.FinancialProfileSaved);
        
    }

    public async Task<IResult> DeleteAsync(string id)
    {
        var financialProfile = await _financialProfileDal.GetAsync(x => x.UserId == id);
        if (financialProfile == null)
        {
            return new ErrorResult(Messages.FinancialProfileNotFound);
        }
        await _financialProfileDal.DeleteAsync(financialProfile);
        return new SuccessResult(Messages.FinancialProfileDeleted);
    }

    private static FinancialProfileResponse MapToResponse(FinancialProfile entity) => new()
    {
        Id = entity.Id,
        UserId = entity.UserId,
        MonthlyIncome = entity.MonthlyIncome,
        MonthlyExpenses = entity.MonthlyExpenses,
        MonthlyDebtPayment = entity.MonthlyDebtPayment,
        TotalDebt = entity.TotalDebt,
        CashReserve = entity.CashReserve,
        InvestmentAmount = entity.InvestmentAmount,
        RiskPreference = entity.RiskPreference,
        CreatedAt = entity.CreatedAt,
        UpdatedAt = entity.UpdatedAt
    };

     private static FinancialProfile MapToEntity(string userId, UpsertFinancialProfileRequest request) => new()
    {
        UserId = userId,
        MonthlyIncome = request.MonthlyIncome,
        MonthlyExpenses = request.MonthlyExpenses,
        MonthlyDebtPayment = request.MonthlyDebtPayment,
        TotalDebt = request.TotalDebt,
        CashReserve = request.CashReserve,
        InvestmentAmount = request.InvestmentAmount,
        RiskPreference = request.RiskPreference,
        UpdatedAt = DateTime.UtcNow
    };

    public async Task<IDataResult<FinancialIqCalculateResponse>> CalculateIqAsync(string userId)
    {
        var profile = await _financialProfileDal.GetAsync(x => x.UserId == userId);
        if (profile == null)
        {
            return new ErrorDataResult<FinancialIqCalculateResponse>(Messages.FinancialProfileNotFound);
        }
        var iqRequest = new FinancialIqCalculateRequest
        {   UserId = profile.UserId,
            MonthlyIncome = profile.MonthlyIncome,
            MonthlyExpenses = profile.MonthlyExpenses,
            MonthlyDebtPayment = profile.MonthlyDebtPayment,
            CashReserve = profile.CashReserve
        };
        return await _financialIqClient.CalculateAsync(iqRequest);
    }
}