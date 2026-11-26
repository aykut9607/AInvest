using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;

namespace FinancialIQ.Tests;

// the two building blocks of scoring v3: the piecewise-linear share and the two-step half-up rounding of the points
public class LinearScaleTests
{
    [Theory]
    [InlineData(-1, 0)]       // below the first anchor: its share
    [InlineData(0, 0)]
    [InlineData(1.5, 0.3)]    // halfway to 3 months
    [InlineData(3, 0.6)]
    [InlineData(4.5, 0.8)]
    [InlineData(6, 1)]
    [InlineData(99, 1)]       // above the last anchor: its share
    public void IncreasingScale_IsLinearBetweenAnchorsAndClampedOutside(double months, double share)
    {
        Assert.Equal((decimal)share, ScoringRules.CashReserveMonths.Scale.Share((decimal)months));
    }

    [Theory]
    [InlineData(0.05, 1)]
    [InlineData(0.10, 1)]
    [InlineData(0.15, 0.8)]
    [InlineData(0.20, 0.6)]
    [InlineData(0.28, 0.4)]
    [InlineData(0.36, 0.2)]
    [InlineData(0.43, 0.1)]
    [InlineData(0.50, 0)]
    [InlineData(2, 0)]
    public void DecreasingScale_IsLinearBetweenAnchorsAndClampedOutside(double ratio, double share)
    {
        Assert.Equal((decimal)share, ScoringRules.InstallmentToIncome.Scale.Share((decimal)ratio));
    }

    [Fact]
    public void EveryFactorScale_RunsFrom0To1_PassesTheWarningLine_AndIsAscendingByValue()
    {
        foreach (var factor in ScoringRules.Factors)
        {
            var shares = factor.Scale.Anchors.Select(a => a.Share).ToList();
            Assert.Equal(0m, shares.Min());
            Assert.Equal(1m, shares.Max());
            // the "adequate" step of the ladder is the warning line
            Assert.Contains(ScoringRules.WarningShare, shares);
            var values = factor.Scale.Anchors.Select(a => a.Value).ToList();
            Assert.Equal(values.Order(), values);
            Assert.Equal(values.Count, values.Distinct().Count());
        }
    }

    [Fact]
    public void FactorMaximums_AreThoseOfVariantV3cI5()
    {
        Assert.Equal(
            [KeyValuePair.Create("CashReserveMonths", 30), KeyValuePair.Create("InstallmentToIncome", 25), KeyValuePair.Create("NetDebtToIncome", 10),
             KeyValuePair.Create("SavingsRate", 30), KeyValuePair.Create("Impatience", 5)],
            FinancialIqCommandManager.FactorMaximums.ToList());
    }

    [Theory]
    [InlineData("0", 0)]
    [InlineData("1.5", 2)]
    [InlineData("2.5", 3)]
    [InlineData("12.5", 13)]                               // banker's rounding (C#'s default) would give 12
    [InlineData("2.4999995", 3)]                           // the 6-decimal step first: 2.500000
    [InlineData("2.4999994", 2)]
    [InlineData("2.4999999999999999999999999995", 3)]      // the noise of a division that is 2.5 on paper
    [InlineData("29.5", 30)]
    public void Points_AreRoundedHalfUpInTwoSteps(string value, int expected)
    {
        Assert.Equal(expected, FinancialIqCommandManager.RoundPoints(decimal.Parse(value, System.Globalization.CultureInfo.InvariantCulture)));
    }
}
