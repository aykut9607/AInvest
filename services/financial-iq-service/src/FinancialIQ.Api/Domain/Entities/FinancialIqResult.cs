using FinancialIQ.Api.Domain.Common;
namespace FinancialIQ.Api.Domain.Entities;

public class FinancialIqResult : IEntity
{
    // single source for the user_id column size (DbContext) and the validation rule (FinancialIqManager),
    // same limit as Finance Profile's user_id
    public const int UserIdMaxLength = 100;

    // LOW / MEDIUM / HIGH
    public const int SegmentMaxLength = 10;

    public Guid Id { get; set; }
    public string UserId { get; set; } = string.Empty;
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
    public string FactorBreakdown { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
    public DateTime UpdatedAt { get; set; } = DateTime.UtcNow;
}