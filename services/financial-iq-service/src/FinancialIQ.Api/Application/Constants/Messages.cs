
namespace FinancialIQ.Api.Application.Constants;

public static class Messages
{
    public const string FinancialIqResultNotFound = "Financial IQ result not found.";
    public const string FinancialIqResultRetrieved = "Financial IQ result retrieved successfully.";
    public const string FinancialIqResultCalculated = "Financial IQ score calculated successfully.";
    public const string InvalidMonthlyIncome = "Monthly income must be greater than zero.";
    public const string NegativeAmountNotAllowed = "Monetary fields cannot be negative.";
    public const string InvalidUserId = "User id is required and must be at most 100 characters.";
    public const string InvalidRiskPreference = "Risk preference must be one of LOW, MEDIUM, HIGH.";
    public const string InvalidImpatienceLevel = "Impatience level must be between 1 and 5.";
    public const string FinancialIqHistoryNotFound = "No Financial IQ history found for this user.";
    public const string FinancialIqHistoryRetrieved = "Financial IQ history retrieved successfully.";
    public const string InvalidHistoryTake = "Take must be between 1 and 100.";
}