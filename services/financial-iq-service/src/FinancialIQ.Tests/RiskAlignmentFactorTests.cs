using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;
using System.Text.Json;
using Xunit;

namespace FinancialIQ.Tests;

public class RiskAlignmentFactorTests
{
    // 6 months reserve, 10% debt ratio, 50% savings -> behavioral capacity HIGH
    private static CalculateRequest StrongFinances(string riskPreference) => new()
    {
        UserId = "test-user",
        MonthlyIncome = 10000,
        MonthlyExpenses = 4000,
        MonthlyDebtPayment = 1000,
        CashReserve = 24000,
        RiskPreference = riskPreference
    };

    // same numbers as demo-user-4: ~0.1 months reserve and negative savings -> behavioral capacity LOW
    private static CalculateRequest WeakFinances(string riskPreference) => new()
    {
        UserId = "test-user",
        MonthlyIncome = 30000,
        MonthlyExpenses = 25000,
        MonthlyDebtPayment = 7000,
        CashReserve = 3000,
        RiskPreference = riskPreference
    };

    private static JsonElement Breakdown(CalculateRequest request)
    {
        var (_, _, factorBreakdown) = FinancialIqManager.CalculateScore(request);
        return JsonDocument.Parse(factorBreakdown).RootElement.Clone();
    }

    [Fact]
    public void StatedMatchesBehavior_ShouldGiveFullPointsAndNoFlag()
    {
        var json = Breakdown(StrongFinances("HIGH"));

        Assert.Equal(15, json.GetProperty("factors").GetProperty("RiskAlignment").GetInt32());
        Assert.False(json.GetProperty("riskProfile").GetProperty("inconsistent").GetBoolean());
        Assert.Equal("ALIGNED", json.GetProperty("riskProfile").GetProperty("direction").GetString());
    }

    [Fact]
    public void OneLevelOff_ShouldGivePartialPoints()
    {
        var json = Breakdown(StrongFinances("MEDIUM"));

        Assert.Equal(8, json.GetProperty("factors").GetProperty("RiskAlignment").GetInt32());
    }

    [Fact]
    public void HighStatedWithWeakFinances_ShouldFlagOverstatedAndWarn()
    {
        var json = Breakdown(WeakFinances("HIGH"));
        var riskProfile = json.GetProperty("riskProfile");

        Assert.Equal(0, json.GetProperty("factors").GetProperty("RiskAlignment").GetInt32());
        Assert.Equal("HIGH", riskProfile.GetProperty("stated").GetString());
        Assert.Equal("LOW", riskProfile.GetProperty("behavioral").GetString());
        Assert.True(riskProfile.GetProperty("inconsistent").GetBoolean());
        Assert.Equal("OVERSTATED", riskProfile.GetProperty("direction").GetString());
        Assert.Contains("Stated risk preference exceeds financial capacity",
            json.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()));
    }

    [Fact]
    public void LowStatedWithStrongFinances_ShouldFlagUnderstatedWithoutWarning()
    {
        var json = Breakdown(StrongFinances("LOW"));
        var riskProfile = json.GetProperty("riskProfile");

        Assert.True(riskProfile.GetProperty("inconsistent").GetBoolean());
        Assert.Equal("UNDERSTATED", riskProfile.GetProperty("direction").GetString());
        // being more careful than needed costs points but is not a risk, so no warning
        Assert.Equal(0, json.GetProperty("warnings").GetArrayLength());
    }

    [Theory]
    [InlineData(2, 0.30, -0.05, "LOW")]     // reserve under 3 months
    [InlineData(4, 0.40, 0.15, "LOW")]      // debt ratio over 0.36
    [InlineData(4, 0.15, 0.05, "MEDIUM")]   // nothing alarming, not strong enough for HIGH
    [InlineData(6, 0.20, 0.10, "HIGH")]     // exactly on every HIGH threshold
    public void BehavioralCapacity_ShouldFollowThresholds(double months, double debtRatio, double savingsRate, string expected)
    {
        var capacity = FinancialIqManager.GetBehavioralRiskCapacity((decimal)months, (decimal)debtRatio, (decimal)savingsRate);

        Assert.Equal(expected, capacity);
    }
}
