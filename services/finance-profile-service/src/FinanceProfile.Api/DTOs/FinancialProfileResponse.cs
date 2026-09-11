using FinanceProfile.Api.Domain.Common;
namespace FinanceProfile.Api.DTOs;

public class FinancialProfileResponse: IDto
{
    public Guid Id { get; set; }

    public string UserId { get; set; } = string.Empty;

    public decimal MonthlyIncome { get; set; }

    public decimal MonthlyExpenses { get; set; }

    public decimal MonthlyDebtPayment { get; set; }

    public decimal TotalDebt { get; set; }

    public decimal CashReserve { get; set; }

    public decimal InvestmentAmount { get; set; }

    public string RiskPreference { get; set; } = "MEDIUM";

    public DateTime CreatedAt { get; set; }

    public DateTime UpdatedAt { get; set; }
}