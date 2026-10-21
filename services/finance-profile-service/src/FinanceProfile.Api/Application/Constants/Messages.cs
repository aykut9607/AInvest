namespace FinanceProfile.Api.Application.Constants;

public static class Messages
{
    
    // CRUD - success
    public const string FinancialProfileListed = "Financial profiles listed successfully.";
    public const string FinancialProfileRetrieved = "Financial profile retrieved successfully.";
    public const string FinancialProfileSaved = "Financial profile saved successfully.";    
    public const string FinancialProfileDeleted = "Financial profile deleted successfully.";

    // Not found
    public const string FinancialProfileNotFound = "Financial profile not found.";

    // Validation / business rules
    public const string InvalidMonthlyIncome = "Monthly income must be greater than zero.";
    public const string NegativeAmountNotAllowed = "Monetary fields cannot be negative.";
    public const string InvalidRiskPreference = "Risk preference must be one of the allowed values.";
    public const string InvalidImpatienceLevel = "Impatience level must be between 1 and 5.";
    public const string InvalidUserId = "User id is required and must be at most 100 characters.";

    // Financial IQ service (upstream) failures - returned as 502, the client did nothing wrong
    public const string FinancialIqServiceUnavailable = "Financial IQ service is unavailable. Please try again later.";
    public const string FinancialIqCalculationFailed = "Financial IQ service could not calculate the score.";
    public const string FinancialIqEmptyResult = "Financial IQ service returned an empty result.";
    public const string FinancialIqCalculated = "Financial IQ calculation successful.";
}