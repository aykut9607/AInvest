using FinancialIQ.Api.Domain.Common;

namespace FinancialIQ.Api.Domain.Dtos;

public class CalculateRequest : IDto
{
    public string UserId { get; set; } = string.Empty;
    public decimal MonthlyIncome { get; set; }
    public decimal MonthlyExpenses { get; set; }
    public decimal MonthlyDebtPayment { get; set; }
    public decimal CashReserve { get; set; }
    // TotalDebt and InvestmentAmount default to 0 for older callers that don't send them.
    // TotalDebt: net-debt rule (ScoringRules). InvestmentAmount: half counts as reserve, all of it lowers the net debt
    public decimal TotalDebt { get; set; }
    public decimal InvestmentAmount { get; set; }
    // the self-reported risk preference is no longer an input (scoring v2): the risk the user may take is decided
    // from the score later (Portfolio Service), so it can't be claimed. An old caller still sending it is ignored
    public int ImpatienceLevel { get; set; } = 3;
}
