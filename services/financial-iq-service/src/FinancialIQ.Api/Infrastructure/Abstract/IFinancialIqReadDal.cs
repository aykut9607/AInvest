using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Api.Infrastructure.Abstract;

// read side data access: answers are DTOs built by SQL Server, nothing is tracked or changed
public interface IFinancialIqReadDal
{
    // the user's latest result, or null (dbo.usp_GetLatestIqResult)
    Task<FinancialIqResultResponse?> GetLatestAsync(string userId);

    // the user's last `take` calculations, oldest first (dbo.fn_IqTrend)
    Task<List<IqTrendPointResponse>> GetTrendAsync(string userId, int take);

    // month-by-month payoff of a debt, first month first (dbo.fn_DebtPayoffSchedule, recursive CTE)
    Task<List<DebtPayoffMonth>> GetDebtPayoffScheduleAsync(decimal totalDebt, decimal monthlyPayment, decimal monthlyRate, int maxMonths);
}
