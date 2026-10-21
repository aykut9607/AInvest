namespace FinanceProfile.Api.DTOs;

public class FinancialIqCalculateResponse
{
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
    // passed through from the IQ service as-is (a JSON string) so clients can show why the score is what it is
    public string FactorBreakdown { get; set; } = string.Empty;
}