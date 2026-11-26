using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;
using System.Text.Json;
using Xunit;

namespace FinancialIQ.Tests;

public class FinancialIqManagerTests
{
    [Fact]
    public void Medium_ShouldReturnMediumSegment()
    {
        // 1.6 months of reserve 9 + 16% installment 19 + net debt 0.33 years 10 + 24% savings 30 + impatience 4 -> 1 = 69
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 50000,
            MonthlyExpenses = 30000,
            MonthlyDebtPayment = 8000,
            TotalDebt = 200000,
            CashReserve = 60000,
            ImpatienceLevel = 4
        };

        var (score, segment, _) = FinancialIqCommandManager.CalculateScore(request);

        Assert.Equal("MEDIUM", segment);
        Assert.Equal(69, score);
    }

    [Fact]
    public void HighDebt_ShouldReturnLowSegment()
    {
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 50000,
            MonthlyExpenses = 42000,
            MonthlyDebtPayment = 22000,
            CashReserve = 5000
        };

        var (_, segment, _) = FinancialIqCommandManager.CalculateScore(request);

        Assert.Equal("LOW", segment);
    }

    [Fact]
    public void LowCashReserve_ShouldEarnFewCashPoints_AndTheWarning()
    {
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 60000,
            MonthlyExpenses = 20000,
            MonthlyDebtPayment = 5000,
            CashReserve = 5000   // 5000 / 25000 outflow = 0.2 months
        };

        var (_, _, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);

        // checking the specific factor directly, not the overall segment -
        // the other factors can be strong enough to offset a weak cash reserve in the total score.
        // 0.2 months -> share 0.04 -> 30 x 0.04 = 1.2 -> 1 point (v2: 0, a step)
        using var json = JsonDocument.Parse(factorBreakdown);
        var root = json.RootElement;
        Assert.Equal(1, root.GetProperty("factors").GetProperty("CashReserveMonths").GetInt32());
        Assert.Contains("Low cash reserve", root.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()));
    }

    [Fact]
    public void ZeroExpenses_ShouldNotThrow()
    {
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 40000,
            MonthlyExpenses = 0,
            MonthlyDebtPayment = 0,
            CashReserve = 30000
        };

        var exception = Record.Exception(() => FinancialIqCommandManager.CalculateScore(request));

        Assert.Null(exception);
    }

    [Fact]
    public void ZeroExpenses_AreCountedAsTheExpenseFloor_AndFlagged()
    {
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 40000,
            MonthlyExpenses = 0,
            MonthlyDebtPayment = 0,
            CashReserve = 30000,
        };

        var (_, _, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);

        // expenses below 10% of the income count as 10% (4,000): 30,000 / 4,000 = 7.5 months -> full points,
        // and "Expenses look too low" says the input is suspicious (v2 counted any reserve as 6 months)
        using var json = JsonDocument.Parse(factorBreakdown);
        var root = json.RootElement;
        var warnings = root.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()).ToList();
        Assert.Equal(30, root.GetProperty("factors").GetProperty("CashReserveMonths").GetInt32());
        Assert.DoesNotContain("Low cash reserve", warnings);
        Assert.Contains("Expenses look too low", warnings);
    }

    [Fact]
    public void ZeroExpenses_OneTlOfCash_IsNotAFullReserve()
    {
        // audit G10: in v2, 0 expenses and 0 cash gave 0 points and 1 TL of cash gave the full 25 (a 25-point step)
        var noCash = Scoring.Score(Scoring.Profile(50000, 0, cash: 0));
        var oneTl = Scoring.Score(Scoring.Profile(50000, 0, cash: 1));

        Assert.Equal(noCash.Score, oneTl.Score);
        Assert.Equal(0, oneTl.Factor("CashReserveMonths"));
    }

    [Fact]
    public void PerfectScenario_ShouldProduceValidJsonWithEmptyWarnings()
    {
        // 6 months of reserve, 10% installment on a matching debt, 50% savings, patient
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 10000,
            MonthlyExpenses = 4000,
            MonthlyDebtPayment = 1000,
            TotalDebt = 12000,
            CashReserve = 30000,
            ImpatienceLevel = 1
        };

        var (score, segment, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);

        Assert.Equal(100, score);
        Assert.Equal("HIGH", segment);

        using var json = JsonDocument.Parse(factorBreakdown);
        var warnings = json.RootElement.GetProperty("warnings");
        Assert.Equal(0, warnings.GetArrayLength());
        Assert.Equal(JsonValueKind.Null, json.RootElement.GetProperty("appliedRule").ValueKind);
    }
}
