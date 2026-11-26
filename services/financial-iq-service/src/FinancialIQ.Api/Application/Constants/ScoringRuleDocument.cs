using System.Text.Encodings.Web;
using System.Text.Json;
using System.Text.Json.Serialization;
using static System.FormattableString;

namespace FinancialIQ.Api.Application.Constants;

// the complete rule set of the CURRENT scoring version as one JSON document, built from the same anchor tables
// and constants the scoring code uses. It is what scoring_rule_versions stores for that version
// (ScoringRuleSnapshots) and what GET /api/financial-iq/scoring-rules returns, i.e. the IQ rule table.
// Numbers inside the texts are formatted with the invariant culture (a Turkish machine would write 0,035)
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

    public static RuleSet Current()
    {
        var lifted = string.Join(" and ", ScoringRules.Factors.Where(f => f.LiftedByWealthRunway).Select(f => f.Name));

        return new RuleSet(
            Version: ScoringRules.ScoringVersion,
            MaxScore: 100,
            Segments:
            [
                new("HIGH", ScoringRules.HighSegmentMinScore),
                new("MEDIUM", ScoringRules.MediumSegmentMinScore),
                new("LOW", 0)
            ],
            // in the order they are calculated; every factor and both modifiers name one of these as their measure
            Measures:
            [
                new("liquidAssets", Invariant($"cash + {ScoringRules.InvestmentLiquidShare} x investments")),
                new("effectiveExpenses", Invariant($"max(monthly expenses, {ScoringRules.ExpenseFloorShare} x monthly income)")),
                new("reserveExpenses", Invariant($"max(monthly expenses, {ScoringRules.ExpenseFloorTl} TL)")),
                new("monthlyOutflow", "reserveExpenses + monthly debt payment"),
                new("reserveMonths", "liquidAssets / monthlyOutflow"),
                new("excessLiquidAssets", Invariant($"max(0, liquidAssets - {ScoringRules.ReserveTargetMonths} x monthlyOutflow)")),
                new("netDebt", "max(0, total debt - excessLiquidAssets)"),
                new("netDebtYears", "netDebt / (12 x monthly income)"),
                new("effectiveDebtPayment", Invariant($"max(monthly debt payment, {ScoringRules.InterestFloorMonthlyRate} x netDebt)")),
                new("installmentRatio", "effectiveDebtPayment / monthly income"),
                new("savingsRate", "(monthly income - effectiveExpenses - effectiveDebtPayment) / monthly income"),
                new("liquidNetWorth", "liquidAssets - total debt"),
                new("runwayYears", "liquidNetWorth / (12 x reserveExpenses), 0 when liquidNetWorth <= 0"),
                new("impatienceLevel", "self-reported, 1 (patient) to 5 (impatient)")
            ],
            Interpolation: "share = s0 + (x - x0) x (s1 - s0) / (x1 - x0) between the two anchors around x (anchors ascending by value); " +
                           "below the first anchor its share, above the last anchor its share",
            Factors: ScoringRules.Factors.Select(f => new FactorRules(
                f.Name, f.MaxPoints, f.Scale.Measure, Anchors(f.Scale), f.LiftedByWealthRunway,
                new FactorWarningRules(f.Warning.Text,
                    f.Warning.Severe is { } severe ? new WarningRules(severe.Text, severe.When, severe.Threshold) : null))).ToList(),
            Points: Invariant($"points = maxPoints x share x solvencyCap, rounded half up per factor (first to {ScoringRules.PointsPreRoundingDecimals} decimals, then to an integer); score = sum of the factor points"),
            WarningShare: ScoringRules.WarningShare,
            FactorWarning: "a factor whose points before the solvency cap (maxPoints x share, rounded) are below warningShare x maxPoints gets its warning; " +
                           "the severe text replaces it when the factor's measure meets the severe condition",
            SolvencyCap: new ModifierRules(ScoringRules.SolvencyCap.Measure, Anchors(ScoringRules.SolvencyCap),
                Effect: "multiplies the points of every factor",
                Warning: ScoringRules.ExtremeDebtWarning + " when solvencyCap < 1",
                AppliedRule: ScoringRules.SolvencyCapRule,
                AppliedRuleCondition: "solvencyCap < 1"),
            WealthRunway: new ModifierRules(ScoringRules.WealthRunway.Measure, Anchors(ScoringRules.WealthRunway),
                Effect: $"floor for the share of {lifted}: share = max(own share, runway share)",
                Warning: null,
                AppliedRule: ScoringRules.WealthRunwayRule,
                AppliedRuleCondition: Invariant($"no SOLVENCY_CAP, runwayYears >= {ScoringRules.WealthRunwayLabelMinYears} and the score is higher than the same calculation with a runway share of 0")),
            OtherWarnings:
            [
                new(ScoringRules.InstallmentBelowInterestWarning,
                    Invariant($"netDebt > 0 and monthly debt payment < {ScoringRules.InterestFloorMonthlyRate} x netDebt")),
                new(ScoringRules.ExpensesTooLowWarning, Invariant($"monthly expenses < {ScoringRules.ExpenseFloorShare} x monthly income")),
                new(ScoringRules.InstallmentWithoutDebtWarning, "monthly debt payment > 0 and total debt = 0"),
                new(ScoringRules.InstallmentExceedsDebtWarning, "total debt > 0 and monthly debt payment > total debt")
            ],
            WarningOrder: "factor warnings in factor order, then the solvency cap warning, then otherWarnings in this order; no duplicates",
            AppliedRuleNote: "appliedRule is a label only (SOLVENCY_CAP first, then WEALTH_RUNWAY, otherwise null); the score is always the sum of the factor points");
    }

    private static List<AnchorRules> Anchors(LinearScale scale) => scale.Anchors.Select(a => new AnchorRules(a.Value, a.Share)).ToList();

    public sealed record RuleSet(string Version, int MaxScore, IReadOnlyList<SegmentRules> Segments, IReadOnlyList<MeasureRules> Measures,
        string Interpolation, IReadOnlyList<FactorRules> Factors, string Points, decimal WarningShare, string FactorWarning,
        ModifierRules SolvencyCap, ModifierRules WealthRunway, IReadOnlyList<ConditionRules> OtherWarnings,
        string WarningOrder, string AppliedRuleNote);
    public sealed record SegmentRules(string Name, int MinScore);
    public sealed record MeasureRules(string Name, string Formula);
    public sealed record AnchorRules(decimal Value, decimal Share);
    public sealed record FactorRules(string Name, int MaxPoints, string Measure, IReadOnlyList<AnchorRules> Anchors,
        bool LiftedByWealthRunway, FactorWarningRules Warning);
    public sealed record FactorWarningRules(string Text, WarningRules? Severe);
    public sealed record WarningRules(string Text, string When, decimal Threshold);
    public sealed record ModifierRules(string Measure, IReadOnlyList<AnchorRules> Anchors, string Effect, string? Warning,
        string AppliedRule, string AppliedRuleCondition);
    public sealed record ConditionRules(string Text, string Condition);
}
