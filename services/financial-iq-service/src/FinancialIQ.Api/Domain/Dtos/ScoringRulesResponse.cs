using System.Text.Json;
using FinancialIQ.Api.Domain.Common;

namespace FinancialIQ.Api.Domain.Dtos;

// one scoring version as stored in scoring_rule_versions; Rules is the rule set as a JSON object
// (segments, factors with their tiers and warnings, the special rules), i.e. the data behind the IQ rule table
public class ScoringRulesResponse : IDto
{
    public string Version { get; set; } = string.Empty;
    public string Description { get; set; } = string.Empty;
    public DateTime EffectiveFrom { get; set; }
    public bool IsActive { get; set; }
    public JsonElement Rules { get; set; }
}
