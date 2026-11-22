using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;

namespace FinancialIQ.Api.Application.Constants;

// the complete rule set of the CURRENT scoring version as one JSON document, built from the same ScoreScale
// tables and constants the scoring code uses. It is what scoring_rule_versions stores for that version
// (ScoringRuleSnapshots) and what GET /api/financial-iq/scoring-rules returns, i.e. the IQ rule table.
public static class ScoringRuleDocument
{
    public static readonly JsonSerializerOptions JsonOptions = new()
    {
        PropertyNamingPolicy = JsonNamingPolicy.CamelCase,
        DefaultIgnoreCondition = JsonIgnoreCondition.WhenWritingNull,
        // keep '+', '<', '>' readable in the stored JSON (it is data for people, never embedded in HTML)
        Encoder = JavaScriptEncoder.UnsafeRelaxedJsonEscaping
    };

    public static string CurrentJson() => JsonSerializer.Serialize(Current(), JsonOptions);

    public static RuleSet Current() => new(
        Version: ScoringRules.ScoringVersion,
        MaxScore: 100,
        Segments:
        [
            new("HIGH", ScoringRules.HighSegmentMinScore),
            new("MEDIUM", ScoringRules.MediumSegmentMinScore),
            new("LOW", 0)
        ],
        Factors:
        [
            Factor("CashReserveMonths", null, ScoringRules.CashReserveMonths),
            Factor("DebtToIncomeRatio", "the worse (lower) of the two parts", ScoringRules.InstallmentToIncome, ScoringRules.NetDebtYearsOfIncome),
            Factor("SavingsRate", null, ScoringRules.SavingsRate),
            Factor("ExpenseRatio", null, ScoringRules.ExpenseRatio),
            Factor("Impatience", null, ScoringRules.Impatience)
        ],
        InvestmentReserveShare: ScoringRules.InvestmentReserveShare,
        RuleOrder: "checked in this order before the factors; the first matching rule sets the score and every factor to its maximum (100) or to 0",
        Rules:
        [
            new(ScoringRules.VeryHighIncomeRule, 100,
                $"monthly income >= {ScoringRules.VeryHighMonthlyIncome} and net debt <= {ScoringRules.VeryHighIncomeMaxNetDebtYears} years of income"),
            new(ScoringRules.VeryHighWealthRule, 100,
                $"cash + investments - total debt >= {ScoringRules.VeryHighNetWorth}"),
            new(ScoringRules.ExtremeDebtRule, 0,
                $"total debt - cash - investments >= {ScoringRules.ExtremeNetDebt} and monthly income < {ScoringRules.VeryHighMonthlyIncome}")
        ]);

    private static FactorRules Factor(string name, string? combine, params ScoreScale[] parts) =>
        new(name, parts.Min(p => p.MaxPoints), combine, parts.Select(p => new ScaleRules(
            p.Measure, p.Direction,
            p.Tiers.Select(t => new TierRules(t.Threshold, t.Points)).ToList(),
            p.OtherwisePoints,
            p.Warning is null ? null : new WarningRules(p.Warning.Text, p.Warning.When, p.Warning.Threshold))).ToList());

    public sealed record RuleSet(string Version, int MaxScore, IReadOnlyList<SegmentRules> Segments, IReadOnlyList<FactorRules> Factors,
        decimal InvestmentReserveShare, string RuleOrder, IReadOnlyList<SpecialRule> Rules);
    public sealed record SegmentRules(string Name, int MinScore);
    public sealed record FactorRules(string Name, int MaxPoints, string? Combine, IReadOnlyList<ScaleRules> Parts);
    public sealed record ScaleRules(string Measure, string Direction, IReadOnlyList<TierRules> Tiers, int OtherwisePoints, WarningRules? Warning);
    public sealed record TierRules(decimal Threshold, int Points);
    public sealed record WarningRules(string Text, string When, decimal Threshold);
    public sealed record SpecialRule(string Name, int Score, string Condition);
}
