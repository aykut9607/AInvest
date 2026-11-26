using FinancialIQ.Api.Application.Constants;

namespace FinancialIQ.Tests;

// v3 warnings: a weak factor (below 60% of its maximum) always has one; the v2 texts keep their v2 meaning and line,
// the milder new texts cover the rest; consistency and data-quality warnings flag an input, they never reject it
public class WarningTests
{
    [Fact]
    public void TheV2Texts_KeepTheirV2Lines()
    {
        // the sample weak profile: savings -6.7% (< 0), impatience 5
        var weak = Scoring.Score(Scoring.Profile(30000, 25000, 7000, 90000, 3000, 10000, 5)).Warnings;

        Assert.Contains("Negative savings rate", weak);
        Assert.Contains("High impatience", weak);
        // installment 23%: weak (13 of 25) but not above 36%
        Assert.Contains("Elevated debt burden", weak);
        Assert.DoesNotContain("High debt burden", weak);
    }

    [Fact]
    public void MildlyWeakFactors_GetTheMilderTexts()
    {
        // savings 5%: weak (12 of 30) but not negative; installment exactly 20%: 15 of 25 = the line, no warning;
        // impatience 3: the neutral answer
        var mild = Scoring.Score(Scoring.Profile(40000, 30000, 8000, 100000, 64000, 0, 3)).Warnings;

        Assert.Contains("Low savings rate", mild);
        Assert.DoesNotContain("Negative savings rate", mild);
        Assert.DoesNotContain("Elevated debt burden", mild);
        Assert.DoesNotContain("High impatience", mild);
    }

    [Fact]
    public void NetDebtBetweenOneAndThreeYears_IsElevated_AboveThreeYearsHigh()
    {
        var elevated = Scoring.Score(Scoring.Profile(40000, 16000, 20000, 960000, 0, 0, 2)).Warnings;   // 2 years
        var high = Scoring.Score(Scoring.Profile(40000, 16000, 20000, 1920000, 0, 0, 2)).Warnings;      // 4 years

        Assert.Contains("Elevated total debt", elevated);
        Assert.DoesNotContain("High total debt", elevated);
        Assert.Contains("High total debt", high);
    }

    [Fact]
    public void AnInstallmentBelowTheInterest_IsFlagged()
    {
        // 2,000,000 owed, 2,000 a month: the interest alone is 70,000
        Assert.Contains(ScoringRules.InstallmentBelowInterestWarning,
            Scoring.Score(Scoring.Profile(40000, 16000, 2000, 2000000, 50000, 0, 2)).Warnings);
    }

    [Fact]
    public void AnInstallmentWithoutDebt_IsFlagged()
    {
        Assert.Contains(ScoringRules.InstallmentWithoutDebtWarning,
            Scoring.Score(Scoring.Profile(50000, 30000, 8000, 0, 60000, 0, 3)).Warnings);
    }

    [Fact]
    public void AnInstallmentLargerThanTheWholeDebt_IsFlagged()
    {
        Assert.Contains(ScoringRules.InstallmentExceedsDebtWarning,
            Scoring.Score(Scoring.Profile(50000, 30000, 8000, 5000, 60000, 0, 3)).Warnings);
    }

    [Fact]
    public void ExpensesBelowTheFloor_AreFlagged_AndNoLongerBuyAPerfectScore()
    {
        // audit G5: 0 expenses and 0.01 TL of cash gave 100 in v2; the floor counts 5,000 of expenses
        var result = Scoring.Score(Scoring.Profile(50000, 0, cash: 0.01m, impatience: 1));

        Assert.Equal(70, result.Score);
        Assert.Contains(ScoringRules.ExpensesTooLowWarning, result.Warnings);
    }

    [Fact]
    public void AHealthyProfile_HasNoWarnings()
    {
        // 6 months of reserve, installment 10% of a matching debt, 50% savings, patient
        var result = Scoring.Score(Scoring.Profile(10000, 4000, 1000, 12000, 30000, 0, 1));

        Assert.Equal(100, result.Score);
        Assert.Empty(result.Warnings);
    }
}
