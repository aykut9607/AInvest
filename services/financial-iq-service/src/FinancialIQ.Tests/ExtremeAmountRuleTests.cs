using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using System.Text.Json;
using Xunit;

namespace FinancialIQ.Tests;

// the two rules above the 6 factors (ScoringRules): very high income -> 100, extreme net debt -> 0
public class ExtremeAmountRuleTests
{
    // no cash at all, spends most of the income, impatient and claims LOW risk: the factors alone would score low
    private static CalculateRequest NoReserve(decimal monthlyIncome, decimal totalDebt = 0) => new()
    {
        UserId = "test-user",
        MonthlyIncome = monthlyIncome,
        MonthlyExpenses = monthlyIncome * 0.9m,
        MonthlyDebtPayment = 0,
        CashReserve = 0,
        TotalDebt = totalDebt,
        RiskPreference = "LOW",
        ImpatienceLevel = 5
    };

    // healthy ratios (6 months reserve, 10% debt payment, 50% savings) - the factors alone would score high.
    // Cash 96,000 and no investments, so the net debt is totalDebt - 96,000
    private static CalculateRequest HealthyRatios(decimal totalDebt, decimal investments = 0) => new()
    {
        UserId = "test-user",
        MonthlyIncome = 40000,
        MonthlyExpenses = 16000,
        MonthlyDebtPayment = 4000,
        CashReserve = 96000,
        TotalDebt = totalDebt,
        InvestmentAmount = investments,
        RiskPreference = "MEDIUM",
        ImpatienceLevel = 1
    };

    private static (int score, string segment, JsonElement breakdown) Score(CalculateRequest request)
    {
        var (score, segment, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);
        return (score, segment, JsonDocument.Parse(factorBreakdown).RootElement.Clone());
    }

    private static string? AppliedRule(JsonElement breakdown) => breakdown.GetProperty("appliedRule").GetString();

    private static int FactorSum(JsonElement breakdown) =>
        breakdown.GetProperty("factors").EnumerateObject().Sum(f => f.Value.GetInt32());

    [Fact]
    public void VeryHighIncome_WithoutCash_Scores100()
    {
        var (score, segment, breakdown) = Score(NoReserve(ScoringRules.VeryHighMonthlyIncome));

        Assert.Equal(100, score);
        Assert.Equal("HIGH", segment);
        Assert.Equal(ScoringRules.VeryHighIncomeRule, AppliedRule(breakdown));
        // the bars in the apps must still add up to the score
        Assert.Equal(100, FactorSum(breakdown));
        Assert.Empty(breakdown.GetProperty("warnings").EnumerateArray());
        Assert.Equal("HIGH", breakdown.GetProperty("riskProfile").GetProperty("behavioral").GetString());
    }

    [Fact]
    public void VeryHighIncome_WithNetDebtUpToOneYearOfIncome_Scores100()
    {
        // 12,000,000 debt = exactly one year of a 1,000,000 monthly income
        var (score, _, breakdown) = Score(NoReserve(ScoringRules.VeryHighMonthlyIncome, totalDebt: 12_000_000));

        Assert.Equal(100, score);
        Assert.Equal(ScoringRules.VeryHighIncomeRule, AppliedRule(breakdown));
    }

    [Fact]
    public void VeryHighIncome_WithMoreDebtThanOneYearOfIncome_IsScoredByTheFactors()
    {
        // 1,000,000 a month but 90,000,000 owed (7.5 years): no automatic 100
        var (score, _, breakdown) = Score(NoReserve(ScoringRules.VeryHighMonthlyIncome, totalDebt: 90_000_000));

        Assert.Null(AppliedRule(breakdown));
        Assert.True(score < 50);
        Assert.Contains(ScoringRules.HighTotalDebtWarning, breakdown.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()));
    }

    [Fact]
    public void IncomeJustBelowTheThreshold_IsScoredByTheFactors()
    {
        var (score, _, breakdown) = Score(NoReserve(ScoringRules.VeryHighMonthlyIncome - 1));

        Assert.True(score < 100);
        Assert.Null(AppliedRule(breakdown));
        Assert.Contains("Low cash reserve", breakdown.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()));
    }

    [Fact]
    public void ExtremeNetDebt_WithOrdinaryIncome_Scores0()
    {
        // net debt exactly at the threshold: 100,096,000 - 96,000 cash = 100,000,000
        var (score, segment, breakdown) = Score(HealthyRatios(ScoringRules.ExtremeNetDebt + 96_000));

        Assert.Equal(0, score);
        Assert.Equal("LOW", segment);
        Assert.Equal(ScoringRules.ExtremeDebtRule, AppliedRule(breakdown));
        Assert.Equal(0, FactorSum(breakdown));
        Assert.Contains(ScoringRules.ExtremeDebtWarning, breakdown.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()));
        Assert.Equal("LOW", breakdown.GetProperty("riskProfile").GetProperty("behavioral").GetString());
    }

    [Fact]
    public void NetDebtJustBelowTheThreshold_IsScoredByTheFactors()
    {
        var (score, _, breakdown) = Score(HealthyRatios(ScoringRules.ExtremeNetDebt + 96_000 - 1));

        Assert.True(score > 0);
        Assert.Null(AppliedRule(breakdown));
    }

    [Fact]
    public void LargeDebtCoveredByInvestments_IsNotExtreme()
    {
        // 150,000,000 owed but 500,000,000 invested: the net position is positive, so no zero score
        var (score, _, breakdown) = Score(HealthyRatios(150_000_000, investments: 500_000_000));

        Assert.Null(AppliedRule(breakdown));
        Assert.True(score > 0);
    }

    [Fact]
    public void InvestmentsCountInFullAgainstTheDebt()
    {
        // 100,096,000 debt - 96,000 cash - 1 investment = 99,999,999 net -> just below the threshold
        var (_, _, breakdown) = Score(HealthyRatios(ScoringRules.ExtremeNetDebt + 96_000, investments: 1));

        Assert.Null(AppliedRule(breakdown));
    }

    [Fact]
    public void VeryHighIncomeAndExtremeDebt_NeitherRuleApplies()
    {
        var (_, _, breakdown) = Score(NoReserve(ScoringRules.VeryHighMonthlyIncome, ScoringRules.ExtremeNetDebt));

        Assert.Null(AppliedRule(breakdown));
    }

    [Fact]
    public void AmountsAreNotCapped_HugeIncomeStillScores()
    {
        // the advisor's test: a very large salary must raise the score, not be rejected or cut off
        var (score, _, _) = Score(NoReserve(50_000_000_000m));

        Assert.Equal(100, score);
    }

    [Fact]
    public void OlderCallersWithoutTotalDebt_KeepTheirScore()
    {
        // same numbers as demo-user-4 in the docs (score 6); TotalDebt defaults to 0
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 30000,
            MonthlyExpenses = 25000,
            MonthlyDebtPayment = 7000,
            CashReserve = 3000,
            RiskPreference = "HIGH",
            ImpatienceLevel = 5
        };

        var (score, _, breakdown) = Score(request);

        Assert.Equal(6, score);
        Assert.Null(AppliedRule(breakdown));
    }
}
