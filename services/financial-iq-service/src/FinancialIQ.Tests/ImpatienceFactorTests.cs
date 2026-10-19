using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;
using System.Text.Json;
using Xunit;

namespace FinancialIQ.Tests;

public class ImpatienceFactorTests
{
    private static CalculateRequest WithImpatience(int level) => new()
    {
        UserId = "test-user",
        MonthlyIncome = 10000,
        MonthlyExpenses = 4000,
        MonthlyDebtPayment = 1000,
        CashReserve = 24000,
        ImpatienceLevel = level
    };

    [Theory]
    [InlineData(1, 10)]
    [InlineData(2, 8)]
    [InlineData(3, 5)]
    [InlineData(4, 2)]
    [InlineData(5, 0)]
    public void ImpatienceLevel_ShouldMapToPoints(int level, int expectedPoints)
    {
        var (_, _, factorBreakdown) = FinancialIqManager.CalculateScore(WithImpatience(level));

        using var json = JsonDocument.Parse(factorBreakdown);
        var points = json.RootElement.GetProperty("factors").GetProperty("Impatience").GetInt32();
        Assert.Equal(expectedPoints, points);
    }

    [Theory]
    [InlineData(3, false)]
    [InlineData(4, true)]
    [InlineData(5, true)]
    public void HighImpatience_ShouldAddWarningFromLevelFour(int level, bool expectWarning)
    {
        var (_, _, factorBreakdown) = FinancialIqManager.CalculateScore(WithImpatience(level));

        using var json = JsonDocument.Parse(factorBreakdown);
        var warnings = json.RootElement.GetProperty("warnings").EnumerateArray().Select(w => w.GetString());
        Assert.Equal(expectWarning, warnings.Contains("High impatience"));
    }

    [Fact]
    public void RequestWithoutNewFields_ShouldUseNeutralDefaults()
    {
        // older callers only send the 4 money fields
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 10000,
            MonthlyExpenses = 4000,
            MonthlyDebtPayment = 1000,
            CashReserve = 24000
        };

        var (score, _, factorBreakdown) = FinancialIqManager.CalculateScore(request);

        using var json = JsonDocument.Parse(factorBreakdown);
        Assert.Equal("MEDIUM", json.RootElement.GetProperty("riskProfile").GetProperty("stated").GetString());
        Assert.Equal(5, json.RootElement.GetProperty("factors").GetProperty("Impatience").GetInt32());
        // 75 from the money factors + 8 (MEDIUM vs HIGH capacity) + 5 (impatience 3)
        Assert.Equal(88, score);
    }
}
