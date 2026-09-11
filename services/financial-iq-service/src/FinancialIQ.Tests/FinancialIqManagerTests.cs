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
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 50000,
            MonthlyExpenses = 30000,
            MonthlyDebtPayment = 8000,
            CashReserve = 60000
        };

        var (score, segment, factorBreakdown) = FinancialIqManager.CalculateScore(request);

        Assert.Equal("MEDIUM", segment);
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

        var (score, segment, factorBreakdown) = FinancialIqManager.CalculateScore(request);

        Assert.Equal("LOW", segment);
    }

    [Fact]
    public void LowCashReserve_ShouldReturnZeroPointsForCashFactor()
    {
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 60000,
            MonthlyExpenses = 20000,
            MonthlyDebtPayment = 5000,
            CashReserve = 5000   // 5000/20000 = 0.25 months - less than 1 month
        };

        var (score, segment, factorBreakdown) = FinancialIqManager.CalculateScore(request);

        // checking the specific factor directly, not the overall segment -
        // the other 3 factors can be strong enough to offset a weak cash reserve in the total score
        using var json = JsonDocument.Parse(factorBreakdown);
        var cashReserveScore = json.RootElement.GetProperty("factors").GetProperty("CashReserveMonths").GetInt32();
        Assert.Equal(0, cashReserveScore);
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

        var exception = Record.Exception(() => FinancialIqManager.CalculateScore(request));

        Assert.Null(exception);
    }

    [Fact]
    public void PerfectScenario_ShouldProduceValidJsonWithEmptyWarnings()
    {
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 10000,
            MonthlyExpenses = 4000,
            MonthlyDebtPayment = 1000,
            CashReserve = 24000
        };

        var (score, segment, factorBreakdown) = FinancialIqManager.CalculateScore(request);

        Assert.Equal(100, score);
        Assert.Equal("HIGH", segment);

        using var json = JsonDocument.Parse(factorBreakdown);
        var warnings = json.RootElement.GetProperty("warnings");
        Assert.Equal(0, warnings.GetArrayLength());
    }
}