using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using Xunit;

namespace FinancialIQ.Tests;

// v3 scores the debt twice, as two factors (v2: one factor, the worse of the two): InstallmentToIncome (25) and
// NetDebtToIncome (10). The installment counts at least as the monthly interest of the net debt, and only the liquid
// assets above the 6-month emergency target are taken off the debt
public class DebtLoadTests
{
    // income 40,000 a month = 480,000 a year; installment 2,000 (5%); no cash, so the net debt is the total debt
    private static CalculateRequest Profile(decimal totalDebt, decimal cash = 0, decimal investments = 0, decimal payment = 2000) =>
        Scoring.Profile(40000, 16000, payment, totalDebt, cash, investments, impatience: 1);

    [Theory]
    [InlineData(0, 10)]            // no debt
    [InlineData(240_000, 10)]      // 0.5 year of income: still the full 10
    [InlineData(360_000, 8)]       // 0.75 years: halfway between 100% and 60%
    [InlineData(480_000, 6)]       // 1 year: 60%
    [InlineData(960_000, 4)]       // 2 years: 40%
    [InlineData(1_440_000, 2)]     // 3 years: 20%
    [InlineData(2_400_000, 0)]     // 5 years: 0
    public void NetDebtInYearsOfIncome_SetsTheNetDebtPoints(decimal totalDebt, int expectedPoints)
    {
        Assert.Equal(expectedPoints, Scoring.Score(Profile(totalDebt)).Factor("NetDebtToIncome"));
    }

    [Fact]
    public void SmallInstallment_DoesNotHideALargeDebt()
    {
        // 2,000,000 owed (over 4 years of income) with a 5% installment: the interest alone is 70,000 a month,
        // so the installment counts as 70,000 (175% of the income)
        var result = Scoring.Score(Profile(totalDebt: 2_000_000));

        Assert.Equal(0, result.Factor("InstallmentToIncome"));
        Assert.Equal(1, result.Factor("NetDebtToIncome"));
        Assert.Equal(["Low cash reserve", "High debt burden", "High total debt", "Negative savings rate", "Installment below interest"], result.Warnings);
    }

    [Fact]
    public void AnInstallmentBelowTheInterest_IsScoredAsTheInterest()
    {
        // 400,000 owed: 3.5% interest = 14,000 a month. Declaring 2,000 scores the same installment points as paying 14,000
        var declared = Scoring.Score(Profile(totalDebt: 400_000, payment: 2000));
        var interest = Scoring.Score(Profile(totalDebt: 400_000, payment: 14000));

        Assert.Equal(interest.Factor("InstallmentToIncome"), declared.Factor("InstallmentToIncome"));
        Assert.Equal(6, declared.Factor("InstallmentToIncome"));
        Assert.Contains(ScoringRules.InstallmentBelowInterestWarning, declared.Warnings);
        Assert.DoesNotContain(ScoringRules.InstallmentBelowInterestWarning, interest.Warnings);
    }

    [Fact]
    public void LargeInstallment_StillCountsWhenTheDebtIsSmall()
    {
        // 200,000 owed (0.42 years: full net debt points) but an installment of 40% of income
        var result = Scoring.Score(Profile(totalDebt: 200_000, payment: 16000));

        Assert.Equal(10, result.Factor("NetDebtToIncome"));
        Assert.Equal(4, result.Factor("InstallmentToIncome"));
        Assert.Contains("High debt burden", result.Warnings);
    }

    [Fact]
    public void AModerateInstallment_GetsTheMilderWarning()
    {
        // 25% of the income: below 60% of the points (12 of 25, the line is 15) but not above the 36% line of
        // "High debt burden". 0.6 + (0.25 - 0.20) x (0.2 - 0.6) / (0.36 - 0.20) = 0.475 -> 25 x 0.475 = 11.875 -> 12
        var result = Scoring.Score(Profile(totalDebt: 240_000, payment: 10000));

        Assert.Equal(12, result.Factor("InstallmentToIncome"));
        Assert.Contains("Elevated debt burden", result.Warnings);
        Assert.DoesNotContain("High debt burden", result.Warnings);
    }

    [Fact]
    public void DebtCoveredByLiquidAssetsAboveTheTarget_CountsAsNoDebt()
    {
        // outflow 18,000 a month -> emergency target 108,000; 2,108,000 cash covers the target and the whole debt
        var cash = Scoring.Score(Profile(totalDebt: 2_000_000, cash: 2_108_000));
        // the same with investments: only half of them is liquid (108,000 + 4,000,000 x 0.5 = 2,108,000)
        var invested = Scoring.Score(Profile(totalDebt: 2_000_000, cash: 108_000, investments: 4_000_000));

        Assert.Equal(10, cash.Factor("NetDebtToIncome"));
        Assert.DoesNotContain("High total debt", cash.Warnings);
        Assert.DoesNotContain(ScoringRules.InstallmentBelowInterestWarning, cash.Warnings);
        Assert.Equal(cash.Factors, invested.Factors);
    }

    [Fact]
    public void TheEmergencyReserve_IsNotAlsoTakenOffTheDebt()
    {
        // exactly the 6-month target in cash: it fills the reserve factor, the debt stays 2,000,000 in full
        var m = FinancialIqCommandManager.Measure(Profile(totalDebt: 2_000_000, cash: 108_000));

        Assert.Equal(6m, m.ReserveMonths);
        Assert.Equal(0m, m.ExcessLiquidAssets);
        Assert.Equal(2_000_000m, m.NetDebt);
    }

    [Fact]
    public void HighEarnerDeepInDebt_IsNoLongerScoredMedium()
    {
        // the case from the v2 review: 2,000,000 a month, 150,000,000 net debt (6.25 years), no cash; v2 gave 48
        var request = Scoring.Profile(2_000_000, 500_000, 100_000, 150_000_000, cash: 0, investments: 0, impatience: 2);

        var result = Scoring.Score(request);

        // the interest (5,250,000 a month) takes the installment and savings factors to 0, and the cap (6.25 years ->
        // 0.875) scales what is left: impatience 2 -> 5 x 0.8 x 0.875 = 3.5 -> 4
        Assert.Equal((4, "LOW"), (result.Score, result.Segment));
        Assert.Equal(ScoringRules.SolvencyCapRule, result.AppliedRule);
        Assert.Contains("Extreme total debt", result.Warnings);
    }
}
