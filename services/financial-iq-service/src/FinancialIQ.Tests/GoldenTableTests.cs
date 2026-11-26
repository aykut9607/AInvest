using FinancialIQ.Api.Application.Concrete;

namespace FinancialIQ.Tests;

// scoring v3 is a port of the Python reference (evaluation/iq_v3/scoring.py, variant v3c-i5). Every case of its golden
// table must come out exactly the same here: score, segment, every factor, the factor maximums, the warnings in their
// order and the label. The measures are compared too (rounded to 6 decimals, half up, as in the table): when a case
// fails, the first measure that differs shows which formula was ported wrongly
public class GoldenTableTests
{
    public static TheoryData<string> CaseIds()
    {
        var data = new TheoryData<string>();
        foreach (var c in GoldenTable.Cases) data.Add(c.Id);
        return data;
    }

    [Fact]
    public void TheTableHasAllCases()
    {
        // 10 demo profiles, 17 audit examples, 23 threshold probes (incl. the "+1 TL" side of each pair),
        // 2 cases of the WEALTH_RUNWAY label rule (L1, L2)
        Assert.Equal(52, GoldenTable.Cases.Count);
        Assert.Equal(GoldenTable.Cases.Count, GoldenTable.Cases.Select(c => c.Id).Distinct().Count());
    }

    [Theory]
    [MemberData(nameof(CaseIds))]
    public void Measures_MatchTheReference(string id)
    {
        var golden = GoldenTable.Get(id);
        var m = FinancialIqCommandManager.Measure(golden.Request);

        // the reference's names -> ours
        var actual = new Dictionary<string, decimal>
        {
            ["liquid"] = m.LiquidAssets,
            ["expenses_eff"] = m.EffectiveExpenses,
            ["expenses_reserve"] = m.ReserveExpenses,
            ["outflow"] = m.MonthlyOutflow,
            ["reserve_months"] = m.ReserveMonths,
            ["excess_liquid"] = m.ExcessLiquidAssets,
            ["net_debt"] = m.NetDebt,
            ["net_debt_years"] = m.NetDebtYears,
            ["payment_eff"] = m.EffectiveDebtPayment,
            ["installment_ratio"] = m.InstallmentRatio,
            ["savings_rate"] = m.SavingsRate,
            ["liquid_net_worth"] = m.LiquidNetWorth,
            ["runway_years"] = m.RunwayYears,
            ["runway_share"] = m.RunwayShare,
            ["solvency_cap"] = m.SolvencyCap
        };

        Assert.Equal(golden.Intermediates.Keys.Order(), actual.Keys.Order());
        foreach (var (name, expected) in golden.Intermediates)
        {
            var rounded = Math.Round(actual[name], 6, MidpointRounding.AwayFromZero);
            Assert.True(expected == rounded, $"{id}: {name} is {rounded}, the reference has {expected}");
        }
    }

    [Theory]
    [MemberData(nameof(CaseIds))]
    public void Breakdown_MatchesTheReference(string id)
    {
        var golden = GoldenTable.Get(id);
        var result = Scoring.Score(golden.Request);

        Assert.Equal(golden.Score, result.Score);
        Assert.Equal(golden.Segment, result.Segment);
        Assert.Equal("v3", result.Breakdown.GetProperty("version").GetString());
        // same keys, same order, same points
        Assert.Equal(golden.Factors, result.Factors);
        Assert.Equal(GoldenTable.FactorMaximums, result.FactorMaximums);
        Assert.Equal(golden.Warnings, result.Warnings);
        Assert.Equal(golden.AppliedRule, result.AppliedRule);
    }

    [Theory]
    [InlineData("demo-low", 27, "LOW", null)]
    [InlineData("demo-medium", 71, "HIGH", null)]
    [InlineData("demo-high", 87, "HIGH", null)]
    [InlineData("demo-highdebt", 22, "LOW", null)]
    [InlineData("demo-richincome", 53, "MEDIUM", null)]
    [InlineData("demo-richwealth", 84, "HIGH", "WEALTH_RUNWAY")]
    [InlineData("demo-extremedebt", 0, "LOW", "SOLVENCY_CAP")]
    [InlineData("demo-trend-2", 51, "MEDIUM", null)]
    [InlineData("demo-trend-3", 79, "HIGH", null)]
    [InlineData("demo-trend-4", 97, "HIGH", null)]
    public void DemoProfiles_ScoreAsInTheProposal(string id, int score, string segment, string? rule)
    {
        // IQ_V3_PROPOSAL.md 6.1 (and infra/seed/seed_demo_users.py); demo-trend-1 is demo-low
        var result = Scoring.Score(GoldenTable.Get(id).Request);

        Assert.Equal((score, segment, rule), (result.Score, result.Segment, result.AppliedRule));
    }
}
