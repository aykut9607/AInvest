using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;
using System.Text.Json;
using Xunit;

namespace FinancialIQ.Tests;

// v3: the self-reported impatience is worth 5 points (v2: 10), so claiming patience buys at most 5
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
    [InlineData(1, 5)]
    [InlineData(2, 4)]
    [InlineData(3, 3)]
    [InlineData(4, 1)]
    [InlineData(5, 0)]
    public void ImpatienceLevel_ShouldMapToPoints(int level, int expectedPoints)
    {
        var (_, _, factorBreakdown) = FinancialIqCommandManager.CalculateScore(WithImpatience(level));

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
        // level 3 is the neutral answer: 3 of 5 points is exactly the 60% warning line, so no warning
        var (_, _, factorBreakdown) = FinancialIqCommandManager.CalculateScore(WithImpatience(level));

        using var json = JsonDocument.Parse(factorBreakdown);
        var warnings = json.RootElement.GetProperty("warnings").EnumerateArray().Select(w => w.GetString());
        Assert.Equal(expectWarning, warnings.Contains("High impatience"));
    }

    [Fact]
    public void FromMostImpatientToMostPatient_TheScoreRisesByFive()
    {
        var (impatient, _, _) = FinancialIqCommandManager.CalculateScore(WithImpatience(5));
        var (patient, _, _) = FinancialIqCommandManager.CalculateScore(WithImpatience(1));

        Assert.Equal(5, patient - impatient);
    }

    [Fact]
    public void RequestWithoutNewFields_ShouldUseNeutralDefaults()
    {
        // older callers only send the 4 money fields (and maybe the old risk preference, which is ignored now)
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 10000,
            MonthlyExpenses = 4000,
            MonthlyDebtPayment = 1000,
            CashReserve = 24000
        };

        var (score, _, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);

        using var json = JsonDocument.Parse(factorBreakdown);
        Assert.Equal(3, json.RootElement.GetProperty("factors").GetProperty("Impatience").GetInt32());
        // 90 from the money factors (reserve 4.8 months 25 + installment 10% 25 + no debt 10 + savings 50% 30) + 3 (impatience 3)
        Assert.Equal(93, score);
    }
}
