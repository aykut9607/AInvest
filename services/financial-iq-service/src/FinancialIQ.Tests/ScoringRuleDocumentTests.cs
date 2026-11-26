using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;

namespace FinancialIQ.Tests;

// scoring_rule_versions holds a frozen copy of every version's rules (ScoringRuleSnapshots). These tests make sure
// that copy is the truth: if an anchor, maximum, constant or rule in ScoringRules changes, the document built from the
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
    public void TheCurrentVersion_IsV3()
    {
        Assert.Equal("v3", ScoringRules.ScoringVersion);
        // the migration CorrectScoringRulesV3 writes exactly this text into the v3 row
        Assert.Equal(ScoringRuleSnapshots.V3, ScoringRuleDocument.CurrentJson());
    }

    // SHA-256 of each published snapshot. Results in the database point at these rule sets, so they must never
    // change (v1 and v2 are byte for byte what AddScoringRuleVersions stored). A new rule set is a new version
    [Theory]
    [InlineData("v1", "5C696A7EA382A442D651326DCAC0383DE5D8BE33AF6B2766D64FE55AD0666E55")]
    [InlineData("v2", "08DFC12F0911F5542EB30BC08BCE94A7753A31AA363B7CC85426D46BE58934D2")]
    // v3 was corrected once under the same name on 26 Nov (CorrectScoringRulesV3, the 2,000 TL reserve floor)
    [InlineData("v3", "BDA9D4EF54574C5A1BB7C2D0C65C0E471B5CA84D61144116364A506052D95B62")]
    public void PublishedSnapshots_AreNeverEdited(string version, string sha256)
    {
        var json = ScoringRuleSnapshots.ForVersion(version)!;

        Assert.Equal(sha256, Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(json))));
    }

    [Fact]
    public void TheFirstV3Text_StaysWhatAddScoringRulesV3Inserted()
    {
        // CorrectScoringRulesV3.Down restores it, so it must be byte for byte the 25 Nov text
        Assert.Equal("B819EA86A391126559D0D9836573179079DAB7D0968A94B850FF67F4F7130B35",
            Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(ScoringRuleSnapshots.V3Initial))));
        Assert.DoesNotContain("reserveExpenses", ScoringRuleSnapshots.V3Initial);
        Assert.Contains("\"reserveExpenses\",\"formula\":\"max(monthly expenses, 2000 TL)\"", ScoringRuleSnapshots.V3);
    }

    [Fact]
    public void EverySnapshot_IsValidJson_AndNamesItsOwnVersion()
    {
        Assert.Equal(["v1", "v2", "v3"], ScoringRuleSnapshots.All.Keys);
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

    [Fact]
    public void TheDocument_DescribesTheV3Mechanisms()
    {
        var rules = ScoringRuleDocument.Current();

        Assert.Equal(["CashReserveMonths", "InstallmentToIncome", "NetDebtToIncome", "SavingsRate", "Impatience"], rules.Factors.Select(f => f.Name));
        // every factor and both modifiers are scored on a measure the document defines
        var measures = rules.Measures.Select(m => m.Name).ToHashSet();
        Assert.All(rules.Factors, f => Assert.Contains(f.Measure, measures));
        Assert.Contains(rules.SolvencyCap.Measure, measures);
        Assert.Contains(rules.WealthRunway.Measure, measures);
        Assert.Equal(ScoringRules.SolvencyCapRule, rules.SolvencyCap.AppliedRule);
        Assert.Equal(ScoringRules.WealthRunwayRule, rules.WealthRunway.AppliedRule);
        // the numbers inside the texts are written with a dot whatever the machine's culture (0.035, not 0,035)
        Assert.Contains("0.035 x netDebt", rules.Measures.Single(m => m.Name == "effectiveDebtPayment").Formula);
        // no TL threshold is left: the v2 rules are gone
        Assert.DoesNotContain("VERY_HIGH", ScoringRuleDocument.CurrentJson());
        Assert.DoesNotContain("EXTREME_DEBT", ScoringRuleDocument.CurrentJson());
    }
}
