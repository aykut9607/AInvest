namespace FinancialIQ.Api.Application.Constants;

// one step of a factor's scale: reaching the threshold earns the points
public sealed record Tier(decimal Threshold, int Points);

// when a measured value triggers a warning: "below" = value < threshold, "above" = value > threshold
public sealed record WarningRule(string Text, string When, decimal Threshold)
{
    public const string Below = "below";
    public const string Above = "above";

    public bool Fires(decimal value) => When == Below ? value < Threshold : value > Threshold;
}

// a factor's points as a table instead of a hard-coded switch, so the scoring code and the published rule table
// (scoring_rule_versions, GET /api/financial-iq/scoring-rules) are built from the same numbers and cannot drift apart.
//   AtLeast: higher is better, tiers ordered from the highest threshold down (first one reached wins)
//   AtMost:  lower is better, tiers ordered from the lowest threshold up (first one not exceeded wins)
//example lets say CashReserveMonths is AtLeast [6 -> 25, 3 -> 15, 1 -> 8], otherwise 0: 4.2 months -> 15 points
public sealed record ScoreScale(string Measure, string Direction, IReadOnlyList<Tier> Tiers, int OtherwisePoints, WarningRule? Warning)
{
    public const string AtLeast = "atLeast";
    public const string AtMost = "atMost";

    public int MaxPoints => Tiers.Count == 0 ? OtherwisePoints : Math.Max(Tiers.Max(t => t.Points), OtherwisePoints);

    public int Points(decimal value)
    {
        foreach (var tier in Tiers)
        {
            var reached = Direction == AtLeast ? value >= tier.Threshold : value <= tier.Threshold;
            if (reached) return tier.Points;
        }
        return OtherwisePoints;
    }
}
