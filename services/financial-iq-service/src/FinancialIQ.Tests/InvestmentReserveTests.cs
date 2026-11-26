using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using Xunit;

namespace FinancialIQ.Tests;

// factor 1 (CashReserveMonths, 30): liquid assets (cash + half of the investments, ScoringRules.InvestmentLiquidShare)
// over the monthly outflow (expenses + installment); 3 months 60%, 6 months 100%, linear in between
public class InvestmentReserveTests
{
    // income 20,000, expenses 10,000 a month, installment 1,000 -> outflow 11,000
    private static CalculateRequest Profile(decimal cash, decimal investments) =>
        Scoring.Profile(20000, 10000, payment: 1000, debt: 0, cash: cash, investments: investments, impatience: 1);

    private static int ReservePoints(CalculateRequest request) => Scoring.Score(request).Factor("CashReserveMonths");

    [Fact]
    public void NoInvestments_CashAlone()
    {
        // 33,000 cash / 11,000 outflow = 3 months -> 60% of 30 = 18 points
        Assert.Equal(18, ReservePoints(Profile(cash: 33000, investments: 0)));
    }

    [Fact]
    public void BetweenTwoAnchors_ThePointsAreProportional()
    {
        // 49,500 / 11,000 = 4.5 months, halfway between 3 (60%) and 6 (100%) -> 80% of 30 = 24 (v2: a 15-point step)
        Assert.Equal(24, ReservePoints(Profile(cash: 49500, investments: 0)));
    }

    [Fact]
    public void HalfOfTheInvestmentsCountsAsReserve()
    {
        // 132,000 invested * 0.5 = 66,000 = 6 months of outflow -> full 30 points
        Assert.Equal(30, ReservePoints(Profile(cash: 0, investments: 132000)));
    }

    [Fact]
    public void InvestmentsDoNotCountInFull()
    {
        // 66,000 * 0.5 = 33,000 -> 3 months -> 18 points (in full they would be 6 months -> 30)
        Assert.Equal(18, ReservePoints(Profile(cash: 0, investments: 66000)));
    }

    [Fact]
    public void CashAndInvestmentsAddUp()
    {
        // 44,000 cash + 44,000 * 0.5 = 66,000 -> 6 months
        Assert.Equal(30, ReservePoints(Profile(cash: 44000, investments: 44000)));
    }

    [Fact]
    public void InvestmentsRemoveTheLowReserveWarning()
    {
        Assert.Contains("Low cash reserve", Scoring.Score(Profile(cash: 0, investments: 0)).Warnings);
        Assert.DoesNotContain("Low cash reserve", Scoring.Score(Profile(cash: 0, investments: 132000)).Warnings);
    }

    [Fact]
    public void TheInstallmentIsPartOfTheOutflow()
    {
        // audit G8: 30,000 cash, expenses 5,000, installment 7,000. v2 divided by the expenses only (6 months, full points,
        // 78 HIGH); v3 divides by what really leaves the account: 30,000 / 12,000 = 2.5 months -> 50% of 30 = 15
        var result = Scoring.Score(Scoring.Profile(20000, 5000, payment: 7000, debt: 0, cash: 30000));

        Assert.Equal(15, result.Factor("CashReserveMonths"));
        Assert.Equal((64, "MEDIUM"), (result.Score, result.Segment));
    }

    [Fact]
    public void DocumentedSampleProfile_Scores27()
    {
        // the sample profile in the docs (CLAUDE.md 6.7), v2: 8. Liquid 3,000 + 10,000 * 0.5 = 8,000 / 32,000 outflow
        // = 0.25 months -> 2 points; installment 23% -> 13; net debt 0.25 years -> 10; savings -6.7% -> 2; impatience 5 -> 0
        var request = Scoring.Profile(30000, 25000, payment: 7000, debt: 90000, cash: 3000, investments: 10000, impatience: 5);

        var result = Scoring.Score(request);

        Assert.Equal((27, "LOW"), (result.Score, result.Segment));
        Assert.Equal([2, 13, 10, 2, 0], result.Factors.Select(f => f.Value));
        Assert.Equal(["Low cash reserve", "Elevated debt burden", "Negative savings rate", "High impatience"], result.Warnings);
    }

    [Fact]
    public void TheLiquidShare_IsHalf()
    {
        Assert.Equal(0.5m, ScoringRules.InvestmentLiquidShare);
    }
}
