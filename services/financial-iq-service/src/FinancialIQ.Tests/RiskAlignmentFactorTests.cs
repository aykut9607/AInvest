using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using System.Text.Json;
using Xunit;

namespace FinancialIQ.Tests;

// Scoring v2: the self-reported risk preference (RiskAlignment factor + riskProfile) was removed.
// The user now picks a risk level later, capped by the score (Portfolio Service), so it no longer changes the score.
// These tests keep it from coming back and cover the problem it caused (better finances could lower the score).
public class RiskAlignmentFactorTests
{
    private static CalculateRequest Profile(decimal cash, decimal expenses = 4000) => new()
    {
        UserId = "test-user",
        MonthlyIncome = 10000,
        MonthlyExpenses = expenses,
        MonthlyDebtPayment = 1000,
        CashReserve = cash,
        ImpatienceLevel = 3
    };

    private static (int score, JsonElement breakdown) Score(CalculateRequest request)
    {
        var (score, _, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);
        return (score, JsonDocument.Parse(factorBreakdown).RootElement.Clone());
    }

    [Fact]
    public void Breakdown_HasNoRiskFactorAndNoRiskProfile()
    {
        var (_, breakdown) = Score(Profile(cash: 24000));

        Assert.False(breakdown.GetProperty("factors").TryGetProperty("RiskAlignment", out _));
        Assert.False(breakdown.TryGetProperty("riskProfile", out _));
        Assert.DoesNotContain("Stated risk preference exceeds financial capacity",
            breakdown.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()));
    }

    [Fact]
    public void Breakdown_CarriesTheScoringVersion()
    {
        var (_, breakdown) = Score(Profile(cash: 24000));

        Assert.Equal(ScoringRules.ScoringVersion, breakdown.GetProperty("version").GetString());
    }

    [Fact]
    public void FactorMaximums_AddUpTo100()
    {
        Assert.Equal(100, FinancialIqCommandManager.FactorMaximums.Values.Sum());
        Assert.Equal(5, FinancialIqCommandManager.FactorMaximums.Count);
    }

    [Fact]
    public void MoreCash_NeverLowersTheScore()
    {
        // v1 lowered some scores when the finances improved (the risk capacity rose past the stated risk)
        var previous = -1;
        foreach (var cash in new decimal[] { 0, 2000, 4000, 8000, 12000, 16000, 24000, 48000, 1_000_000 })
        {
            var (score, _) = Score(Profile(cash));
            Assert.True(score >= previous, $"cash {cash}: score {score} < previous {previous}");
            previous = score;
        }
    }

    [Fact]
    public void LowerExpenses_NeverLowerTheScore()
    {
        var previous = -1;
        foreach (var expenses in new decimal[] { 9000, 8000, 6000, 5000, 4000, 2000, 0 })
        {
            var (score, _) = Score(Profile(cash: 12000, expenses: expenses));
            Assert.True(score >= previous, $"expenses {expenses}: score {score} < previous {previous}");
            previous = score;
        }
    }
}
