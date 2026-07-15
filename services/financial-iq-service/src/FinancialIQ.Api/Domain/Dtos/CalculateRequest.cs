using FinancialIQ.Api.Core.Entities;

namespace FinancialIQ.Api.Domain.Dtos;

public class CalculateRequest : IDto
{
    public string UserId { get; set; } = string.Empty;
    public decimal MonthlyIncome { get; set; }
    public decimal MonthlyExpenses { get; set; }
    public decimal MonthlyDebtPayment { get; set; }
    public decimal CashReserve { get; set; }
}