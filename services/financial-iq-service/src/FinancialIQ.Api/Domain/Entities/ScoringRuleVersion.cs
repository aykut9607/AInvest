using FinancialIQ.Api.Domain.Common;
namespace FinancialIQ.Api.Domain.Entities;

// one row per scoring version (v1, v2, ...): the full rule set it scored with, frozen. Every result and history row
// says which version produced it (scoring_version), so an old score can always be explained by the rules of its day.
// Exactly one version is active (filtered unique index); new calculations use that one
public class ScoringRuleVersion : IEntity
{
    public const int VersionMaxLength = 10;

    public string Version { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    // ScoringRuleSnapshots.Vn: segments, factors with their tiers and warnings, the special rules
    public string RulesJson { get; set; } = string.Empty;
    public DateTime EffectiveFrom { get; set; }
    public bool IsActive { get; set; }
}
