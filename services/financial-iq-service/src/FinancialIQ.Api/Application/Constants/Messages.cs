
namespace FinancialIQ.Api.Application.Constants;

public static class Messages
{
    public const string FinancialIqResultNotFound = "Financial IQ result not found.";
    public const string FinancialIqResultRetrieved = "Financial IQ result retrieved successfully.";
    public const string FinancialIqResultCalculated = "Financial IQ score calculated successfully.";
    public const string InvalidMonthlyIncome = "Monthly income must be greater than zero.";
    public const string NegativeAmountNotAllowed = "Monetary fields cannot be negative.";
    public const string InvalidUserId = "User id is required and must be at most 100 characters.";
    public const string InvalidImpatienceLevel = "Impatience level must be between 1 and 5.";
    public const string FinancialIqHistoryNotFound = "No Financial IQ history found for this user.";
    public const string FinancialIqHistoryRetrieved = "Financial IQ history retrieved successfully.";
    public const string InvalidHistoryTake = "Take must be between 1 and 100.";
    public const string AmountTooLarge = "Monetary fields must be at most 999,999,999,999,999.";
    public const string InvalidMonthlyInterestRate = "Monthly interest rate must be between 0 and 1 (0.035 = 3.5% a month).";
    public const string DebtPayoffCalculated = "Debt payoff schedule calculated successfully.";
    public const string NoDebtToPayOff = "There is no debt to pay off.";
    public const string PaymentDoesNotCoverInterest = "The monthly payment does not cover the monthly interest, so the debt never gets smaller.";
    public const string DebtNotPaidOffWithinLimit = "The debt is not paid off within 600 months (50 years) with this payment.";
}