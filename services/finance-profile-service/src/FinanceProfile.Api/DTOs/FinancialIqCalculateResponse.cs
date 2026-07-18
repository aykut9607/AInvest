namespace FinanceProfile.Api.DTOs;

public class FinancialIqCalculateResponse
{
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
}