namespace FinanceProfile.Api.DTOs;

// body of IQ's POST /api/financial-iq/debt-payoff, filled from the saved profile
public class FinancialIqDebtPayoffRequest
{
    public decimal TotalDebt { get; set; }
    public decimal MonthlyPayment { get; set; }
    // null = IQ's default rate (DebtPayoffRules.DefaultMonthlyInterestRate, 3.5% a month)
    public decimal? MonthlyInterestRate { get; set; }
}
