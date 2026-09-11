using FinancialIQ.Api.Domain.Common;
namespace FinancialIQ.Api.Domain.Entities;

public class FinancialIqResult : IEntity
{
    public Guid Id { get; set; }
    public string UserId { get; set; } = string.Empty;
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
    public string FactorBreakdown { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}