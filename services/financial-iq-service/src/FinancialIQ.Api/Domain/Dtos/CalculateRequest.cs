using FinancialIQ.Api.Domain.Common;

namespace FinancialIQ.Api.Domain.Dtos;

public class CalculateRequest : IDto
{
    public string UserId { get; set; } = string.Empty;
    public decimal MonthlyIncome { get; set; }
    public decimal MonthlyExpenses { get; set; }
    public decimal MonthlyDebtPayment { get; set; }
    public decimal CashReserve { get; set; }
    // defaults keep older callers (that only send the 4 money fields) working
    public string RiskPreference { get; set; } = "MEDIUM";
    public int ImpatienceLevel { get; set; } = 3;
}