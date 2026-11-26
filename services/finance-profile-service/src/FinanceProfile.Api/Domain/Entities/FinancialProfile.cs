using FinanceProfile.Api.Domain.Common;

namespace FinanceProfile.Api.Domain.Entities;

public class FinancialProfile:IEntity
{
    // single source for the user_id column size (DbContext) and the validation rule (FinancialProfileManager)
    public const int UserIdMaxLength = 100;

    // NOT a business limit (any realistic income or debt is accepted and scored): the amount columns are
    // numeric(18,2), which can't hold 10^16 or more, and a bigger value would fail in Postgres with a 500
    public const decimal MaxAmount = 999_999_999_999_999m;

    // allowed answers of the payment discipline questions; single source for the validation
    // (FinancialProfileManager) and the check constraints (FinanceDbContext)
    public const int PaymentAnswerMaxLength = 20;
    public static readonly string[] BillsOnTimeValues = ["ALL", "ALMOST_ALL", "MOST", "SOME", "VERY_FEW"];
    public static readonly string[] MinimumPaymentMonthsValues = ["NONE", "ONE_TWO", "THREE_FIVE", "SIX_PLUS", "NO_CARD"];
    public static readonly string[] LatePaymentsValues = ["NONE", "ONCE", "TWICE_OR_MORE"];

    public Guid Id { get; set; }
    public string UserId { get; set; } = string.Empty;
    public decimal MonthlyIncome { get; set; }
    public decimal MonthlyExpenses { get; set; }
    public decimal MonthlyDebtPayment{ get; set; }
    public decimal TotalDebt { get; set; }
    public decimal CashReserve { get; set; }
    public decimal InvestmentAmount { get; set; }
    // optional since scoring v2: no longer an IQ input. The risk level the user may choose moves to the
    // Portfolio Service (capped by the score); the column stays until then so existing answers are not lost
    public string? RiskPreference { get; set; }
    // self-reported, 1 = can wait years for a return, 5 = wants results right away
    public int ImpatienceLevel { get; set; } = 3;

    // payment discipline (optional, null = not answered). Collected and shown only: NOT sent to Financial IQ
    // and does not change the score yet (planned for a later scoring version after validation)
    // "How often do you pay your bills and debt payments on time?" (FinHealth Score item)
    public string? BillsOnTime { get; set; }
    // months in the last 12 in which only the credit card minimum was paid
    public string? MinimumPaymentMonths { get; set; }
    // payments more than 30 days late in the last 12 months
    public string? LatePayments { get; set; }

    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;


}