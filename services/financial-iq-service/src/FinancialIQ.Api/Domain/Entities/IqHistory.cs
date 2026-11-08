using FinancialIQ.Api.Domain.Common;
namespace FinancialIQ.Api.Domain.Entities;

// one row per calculation, never updated: financial_iq_results keeps only the latest score,
// this table keeps every score so a trend can be shown (written by usp_SaveIqResult)
public class IqHistory : IEntity
{
    public long Id { get; set; }
    public string UserId { get; set; } = string.Empty;
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
    public string FactorBreakdown { get; set; } = string.Empty;
    public DateTime CalculatedAt { get; set; }
}
