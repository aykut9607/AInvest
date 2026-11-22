using System.Text.Json;
using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;

namespace FinancialIQ.Tests;

// scoring_rule_versions holds a frozen copy of every version's rules (ScoringRuleSnapshots). These tests make sure
// that copy is the truth: if a threshold, point value or rule in ScoringRules changes, the document built from the
// code no longer equals the stored snapshot of ScoringVersion, and the fix is a NEW version, not an edited snapshot
public class ScoringRuleDocumentTests
{
    [Fact]
    public void CurrentRules_AreExactlyTheStoredSnapshotOfTheCurrentVersion()
    {
        var fromCode = JsonDocument.Parse(ScoringRuleDocument.CurrentJson()).RootElement;
        var stored = JsonDocument.Parse(ScoringRuleSnapshots.ForVersion(ScoringRules.ScoringVersion)!).RootElement;

        Assert.True(JsonElement.DeepEquals(fromCode, stored),
            "The scoring rules changed but ScoringVersion did not. Raise ScoringRules.ScoringVersion, add a snapshot " +
            "and a migration that inserts it. Rules built from the code: " + ScoringRuleDocument.CurrentJson());
    }

    [Fact]
    public void EverySnapshot_IsValidJson_AndNamesItsOwnVersion()
    {
        foreach (var (version, json) in ScoringRuleSnapshots.All)
        {
            var root = JsonDocument.Parse(json).RootElement;
            Assert.Equal(version, root.GetProperty("version").GetString());
        }
    }

    [Fact]
    public void FactorMaximums_InTheDocument_AddUpTo100()
    {
        var total = ScoringRuleDocument.Current().Factors.Sum(f => f.MaxPoints);

        Assert.Equal(100, total);
        Assert.Equal(FinancialIqCommandManager.FactorMaximums.Values.Sum(), total);
    }

    [Theory]
    [InlineData(6, 25)]
    [InlineData(5.99, 15)]
    [InlineData(3, 15)]
    [InlineData(1, 8)]
    [InlineData(0.99, 0)]
    public void AtLeastScale_GivesThePointsOfTheFirstThresholdReached(double months, int expected)
    {
        Assert.Equal(expected, ScoringRules.CashReserveMonths.Points((decimal)months));
    }

    [Theory]
    [InlineData(0.10, 25)]
    [InlineData(0.1001, 15)]
    [InlineData(0.36, 8)]
    [InlineData(0.37, 0)]
    public void AtMostScale_GivesThePointsOfTheFirstThresholdNotExceeded(double ratio, int expected)
    {
        Assert.Equal(expected, ScoringRules.InstallmentToIncome.Points((decimal)ratio));
    }
}
