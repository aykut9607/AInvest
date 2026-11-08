using FinancialIQ.Api.Domain.Common;

namespace FinancialIQ.Api.Domain.Dtos;

// one calculation in a user's score history, as returned by dbo.fn_IqTrend
public class IqTrendPointResponse : IDto
{
    public DateTime CalculatedAt { get; set; }
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
    // difference to the previous calculation; null for the first one
    public int? ScoreChange { get; set; }
    // average of this score and the 2 before it
    public decimal MovingAverage3 { get; set; }
}
