using System.Text.Json;

namespace FinanceProfile.Api.DTOs;

public class FinancialIqCalculateResponse
{
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
    // passed through from the IQ service as-is so clients can show why the score is what it is.
    // Contract v2: a JSON object { version, factors, warnings, appliedRule } (v1 was a JSON string)
    public JsonElement FactorBreakdown { get; set; }
}