using FinanceProfile.Api.Domain.Common;

namespace FinanceProfile.Api.Domain.Entities;

public class FinancialProfile:IEntity
{
    public Guid Id { get; set; }
    public string UserId { get; set; } = string.Empty;
    public decimal MonthlyIncome { get; set; }
    public decimal MonthlyExpenses { get; set; }
    public decimal MonthlyDebtPayment{ get; set; }
    public decimal TotalDebt { get; set; }
    public decimal CashReserve { get; set; }
    public decimal InvestmentAmount { get; set; }
    public string RiskPreference { get; set; } = "MEDIUM";
    // self-reported, 1 = can wait years for a return, 5 = wants results right away
    public int ImpatienceLevel { get; set; } = 3;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;


}