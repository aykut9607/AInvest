using System.Text.Json;
using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Tests;

// v2.1: no cliffs between the special rules and the factors; 0 is a valid amount everywhere
public class CliffFreeTests
{
    private static (int score, string? rule) Score(decimal income, decimal expenses, decimal payment = 0, decimal debt = 0, decimal cash = 0, decimal investments = 0, int impatience = 3)
    {
        var (score, _, json) = FinancialIqCommandManager.CalculateScore(new CalculateRequest
        {
            UserId = "u", MonthlyIncome = income, MonthlyExpenses = expenses, MonthlyDebtPayment = payment, TotalDebt = debt,
            CashReserve = cash, InvestmentAmount = investments, ImpatienceLevel = impatience
        });
        var b = JsonDocument.Parse(json).RootElement;
        return (score, b.GetProperty("adjustment").ValueKind == JsonValueKind.Object ? b.GetProperty("adjustment").GetProperty("rule").GetString() : null);
    }

    [Fact]
    public void OnlyDebt_NothingElse_Scores0()
    {
        Assert.Equal((0, ScoringRules.DebtCapRule), Score(0, 0, debt: 500_000));
        Assert.Equal(0, Score(0, 5_000, debt: 50_000, impatience: 1).score);
    }

    [Fact]
    public void TwoMillionOfDebtOnAnIncomeOf50000_IsLow()
    {
        var (score, _) = Score(50_000, 20_000, 10_000, 2_000_000, 20_000);
        Assert.InRange(score, 1, 40);
    }

    [Fact]
    public void AMillionOfInvestmentsWithLittleCash_IsNearTheTop()
    {
        Assert.InRange(Score(40_000, 20_000, cash: 5_000, investments: 1_000_000, impatience: 2).score, 90, 100);
    }

    [Fact]
    public void NoIncomeButWealth_IsScoredFromTheWealth()
    {
        // a retiree: 6,000,000 net, 15,000 a month -> 6,000,000 / (25 x 180,000) = 1.33 -> 100
        Assert.Equal((100, ScoringRules.WealthFloorRule), Score(0, 15_000, cash: 1_000_000, investments: 5_000_000));
    }

    [Fact]
    public void NoIncomeNoDebtNoAssets_IsLowButNotAnError()
    {
        Assert.InRange(Score(0, 0, impatience: 1).score, 0, 40);
    }

    [Theory]
    [InlineData(500_000, 50)]
    [InlineData(900_000, 90)]
    [InlineData(999_999, 99)]
    public void TheIncomeFloorRisesSmoothlyTowardsTheRule(int income, int floor)
    {
        Assert.True(Score(income, income * 0.99m, impatience: 5).score >= floor);
    }

    [Fact]
    public void MoreWealthNeverScoresLess_AndThereIsNoCliffAt10Million()
    {
        var last = 0;
        foreach (var investments in new[] { 0m, 500_000m, 1_000_000m, 3_000_000m, 6_000_000m, 9_900_000m, 9_999_999m, 10_000_000m, 50_000_000m })
        {
            var score = Score(20_000, 19_000, investments: investments, impatience: 5).score;
            Assert.True(score >= last, $"{investments}: {score} < {last}");
            last = score;
        }
        Assert.True(Score(20_000, 19_000, investments: 9_900_000m, impatience: 5).score >= 95);
    }

    [Fact]
    public void MoreDebtNeverScoresMore_AndThereIsNoCliffAt100Million()
    {
        var last = 101;
        foreach (var debt in new[] { 0m, 500_000m, 2_000_000m, 5_000_000m, 20_000_000m, 99_000_000m, 100_000_000m, 500_000_000m })
        {
            var score = Score(40_000, 16_000, 4_000, debt, 96_000, impatience: 1).score;
            Assert.True(score <= last, $"{debt}: {score} > {last}");
            last = score;
        }
        Assert.Equal(0, Score(40_000, 16_000, 4_000, 99_000_000, impatience: 1).score);
    }
}
