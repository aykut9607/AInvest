using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using System.Text.Json;
using Xunit;

namespace FinancialIQ.Tests;

// factor 2 takes the worse of two measures: installment / income and net debt / yearly income
public class DebtLoadTests
{
    // income 40,000 a month = 480,000 a year; installment 2,000 (5%) -> 20 points on the installment alone
    private static CalculateRequest Profile(decimal totalDebt, decimal cash = 0, decimal investments = 0) => new()
    {
        UserId = "test-user",
        MonthlyIncome = 40000,
        MonthlyExpenses = 16000,
        MonthlyDebtPayment = 2000,
        TotalDebt = totalDebt,
        CashReserve = cash,
        InvestmentAmount = investments,
        RiskPreference = "MEDIUM",
        ImpatienceLevel = 1
    };

    private static JsonElement Breakdown(CalculateRequest request)
    {
        var (_, _, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);
        return JsonDocument.Parse(factorBreakdown).RootElement.Clone();
    }

    private static int DebtPoints(CalculateRequest request) =>
        Breakdown(request).GetProperty("factors").GetProperty("DebtToIncomeRatio").GetInt32();

    private static string[] Warnings(CalculateRequest request) =>
        Breakdown(request).GetProperty("warnings").EnumerateArray().Select(w => w.GetString()!).ToArray();

    [Theory]
    [InlineData(0, 20)]            // no debt
    [InlineData(240_000, 20)]      // 0.5 year of income
    [InlineData(240_001, 12)]      // just over half a year
    [InlineData(480_000, 12)]      // 1 year
    [InlineData(1_440_000, 6)]     // 3 years
    [InlineData(1_440_001, 0)]     // just over 3 years
    public void NetDebtInYearsOfIncome_SetsTheDebtPoints(decimal totalDebt, int expectedPoints)
    {
        Assert.Equal(expectedPoints, DebtPoints(Profile(totalDebt)));
    }

    [Fact]
    public void SmallInstallment_DoesNotHideALargeDebt()
    {
        // 2,000,000 owed (over 4 years of income) with a 5% installment: the installment alone would give 20
        var request = Profile(totalDebt: 2_000_000);

        Assert.Equal(0, DebtPoints(request));
        Assert.Contains(ScoringRules.HighTotalDebtWarning, Warnings(request));
        Assert.Equal("LOW", Breakdown(request).GetProperty("riskProfile").GetProperty("behavioral").GetString());
    }

    [Fact]
    public void LargeInstallment_StillCountsWhenTheDebtIsSmall()
    {
        // tiny debt but an installment of 40% of income -> the installment decides (0 points)
        var request = Profile(totalDebt: 10_000);
        request.MonthlyDebtPayment = 16000;

        Assert.Equal(0, DebtPoints(request));
        Assert.Contains("High debt burden", Warnings(request));
    }

    [Fact]
    public void DebtCoveredByCashAndInvestments_CountsAsNoDebt()
    {
        // 2,000,000 owed, 500,000 cash + 1,600,000 invested -> net debt below zero
        var request = Profile(totalDebt: 2_000_000, cash: 500_000, investments: 1_600_000);

        Assert.Equal(20, DebtPoints(request));
        Assert.DoesNotContain(ScoringRules.HighTotalDebtWarning, Warnings(request));
    }

    [Fact]
    public void HighCapacityNeedsTheNetDebtWithinOneYearOfIncome()
    {
        // 6+ months reserve (cash 120,000 / 16,000 = 7.5 months), low installment, good savings
        var withinOneYear = Profile(totalDebt: 600_000, cash: 120_000);      // net 480,000 = 1 year
        var overOneYear = Profile(totalDebt: 600_001, cash: 120_000);

        Assert.Equal("HIGH", Breakdown(withinOneYear).GetProperty("riskProfile").GetProperty("behavioral").GetString());
        Assert.Equal("MEDIUM", Breakdown(overOneYear).GetProperty("riskProfile").GetProperty("behavioral").GetString());
    }

    [Fact]
    public void HighEarnerDeepInDebt_IsNoLongerScoredHigh()
    {
        // the case from the review: 2,000,000 a month, 150,000,000 net debt (6.25 years), no cash; was 71 before
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 2_000_000,
            MonthlyExpenses = 500_000,
            MonthlyDebtPayment = 100_000,
            TotalDebt = 150_000_000,
            CashReserve = 0,
            RiskPreference = "MEDIUM",
            ImpatienceLevel = 2
        };

        var (score, segment, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);
        var breakdown = JsonDocument.Parse(factorBreakdown).RootElement;

        // reserve 0 + debt 0 + savings 20 + expenses 15 + risk 8 (MEDIUM vs LOW) + patience 8
        Assert.Equal(51, score);
        Assert.Equal("MEDIUM", segment);
        Assert.Equal(0, breakdown.GetProperty("factors").GetProperty("DebtToIncomeRatio").GetInt32());
        Assert.Equal(JsonValueKind.Null, breakdown.GetProperty("appliedRule").ValueKind);
    }
}
