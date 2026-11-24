namespace FinancialIQ.Api.Application.Constants;

// assumptions of the debt payoff schedule (dbo.fn_DebtPayoffSchedule). The profile has no interest rate field,
// so a default is used; the caller may send its own rate for each request
public static class DebtPayoffRules
{
    // 3.5% a month: an assumption at the level of Turkish consumer-loan / credit-card monthly rates in 2025-2026,
    // not a quoted rate. Taxes on interest (KKDF/BSMV) are not included
    public const decimal DefaultMonthlyInterestRate = 0.035m;

    // 0 is allowed (interest-free installments are common); 1 = 100% a month is the technical upper bound
    public const decimal MaxMonthlyInterestRate = 1m;

    // 50 years: the schedule stops here even if the debt is not paid yet (the recursion needs an end)
    public const int MaxMonths = 600;
}
