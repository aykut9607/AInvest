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

    // SQL Server rowversion: 8 bytes the database sets itself on every INSERT and UPDATE of the row (never written
    // by us). It changes whenever the result changes, so "is the result I based something on still the current one?"
    // is a cheap equality check (see ResultVersion). For EF it is also the concurrency token of this entity
    public byte[] RowVersion { get; set; } = [];

    // the scoring_rule_versions row this score was calculated with (same value as factorBreakdown.version)
    public string ScoringVersion { get; set; } = string.Empty;
}