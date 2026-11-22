using FinancialIQ.Api.Domain.Common;

namespace FinancialIQ.Api.Domain.Dtos;

public class DebtPayoffRequest : IDto
{
    public decimal TotalDebt { get; set; }
    public decimal MonthlyPayment { get; set; }
    // null = DebtPayoffRules.DefaultMonthlyInterestRate; 0.035 means 3.5% a month
    public decimal? MonthlyInterestRate { get; set; }
}

public class DebtPayoffResponse : IDto
{
    public decimal TotalDebt { get; set; }
    public decimal MonthlyPayment { get; set; }
    // the rate actually used (the default when the request had none)
    public decimal MonthlyInterestRate { get; set; }
    // false: the installment does not even cover the interest, or the debt is not paid within MaxMonths
    public bool PaidOff { get; set; }
    // months until the debt is paid; null when PaidOff is false
    public int? Months { get; set; }
    public decimal TotalInterest { get; set; }
    public decimal TotalPaid { get; set; }
    public List<DebtPayoffMonth> Schedule { get; set; } = new();
}

// one row of dbo.fn_DebtPayoffSchedule
public class DebtPayoffMonth : IDto
{
    public int Month { get; set; }
    public decimal OpeningBalance { get; set; }
    public decimal Interest { get; set; }
    public decimal Payment { get; set; }
    public decimal Principal { get; set; }
    public decimal ClosingBalance { get; set; }
}
