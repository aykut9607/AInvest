namespace FinancialIQ.Api.Application.Constants;

// one point of a piecewise-linear scale: at this value of the measure the factor earns this share (0..1) of its maximum
public sealed record Anchor(decimal Value, decimal Share);

// scoring v3: a factor's share as a table of anchors instead of steps, so 1 TL more or less can never make the score
// jump (v2 steps moved it by up to 25 points, the TL rules by up to 100). Anchors are ascending by value.
// Below the first anchor the first share applies, above the last anchor the last share, in between a straight line.
// The scoring code and the published rule table (scoring_rule_versions) are built from the same anchors.
//example lets say the anchors are [0 -> 0, 3 -> 0.6, 6 -> 1]: 1.5 months -> 0.3, 4.5 months -> 0.8, 9 months -> 1
public sealed record LinearScale(string Measure, IReadOnlyList<Anchor> Anchors)
{
    public decimal Share(decimal value)
    {
        if (value <= Anchors[0].Value) return Anchors[0].Share;

        for (var i = 0; i + 1 < Anchors.Count; i++)
        {
            var (from, to) = (Anchors[i], Anchors[i + 1]);
            // the order of operations is part of the rule (same as the Python reference, evaluation/iq_v3/scoring.py):
            // first (value - from) * (share difference), then the division, then the addition
            //example lets say value is 4.5 between 3 -> 0.6 and 6 -> 1: 0.6 + (4.5 - 3) * (1 - 0.6) / (6 - 3) = 0.6 + 0.6 / 3 = 0.8
            if (value <= to.Value) return from.Share + (value - from.Value) * (to.Share - from.Share) / (to.Value - from.Value);
        }

        return Anchors[^1].Share;
    }
}

// the warning of a factor that earned less than ScoringRules.WarningShare of its maximum (before the solvency cap).
// Text is the milder wording; Severe (optional) replaces it when the measure is past the line the same text had in
// v2, so a v2 warning text keeps its v2 meaning and threshold
//example lets say the installment factor is weak: installment 25% of income -> "Elevated debt burden", 40% -> "High debt burden"
public sealed record FactorWarning(string Text, WarningRule? Severe = null)
{
    public string TextFor(decimal measure) => Severe is { } severe && severe.Fires(measure) ? severe.Text : Text;
}

// one of the five v3 factors: key in factorBreakdown, maximum points, its scale, whether the wealth runway can lift it
public sealed record ScoringFactor(string Name, int MaxPoints, LinearScale Scale, bool LiftedByWealthRunway, FactorWarning Warning);
