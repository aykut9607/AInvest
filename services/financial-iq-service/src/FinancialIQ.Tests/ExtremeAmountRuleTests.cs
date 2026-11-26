using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using Xunit;

namespace FinancialIQ.Tests;

// extreme amounts. v2 had three TL rules (VERY_HIGH_INCOME, VERY_HIGH_WEALTH -> 100, EXTREME_DEBT -> 0) and 1 TL across
// one of their lines moved the score by up to 100 points. v3 has no TL threshold: the solvency cap (net debt 5 -> 15 years
// of income) and the wealth runway (liquid net worth in years of expenses) are continuous, and appliedRule only labels them
public class ExtremeAmountRuleTests
{
    // no cash at all, spends 90% of the income and impatient (the v2 VERY_HIGH_INCOME demo when income = 1,000,000)
    private static CalculateRequest NoReserve(decimal monthlyIncome, decimal totalDebt = 0) =>
        Scoring.Profile(monthlyIncome, monthlyIncome * 0.9m, payment: 0, debt: totalDebt, cash: 0, investments: 0, impatience: 5);

    // healthy ratios (6 months reserve, 10% installment, 50% savings) and patient; cash 96,000
    private static CalculateRequest HealthyRatios(decimal totalDebt, decimal investments = 0) =>
        Scoring.Profile(40000, 16000, payment: 4000, debt: totalDebt, cash: 96000, investments: investments, impatience: 1);

    // small salary, spends almost all of it, impatient - but owns a lot
    private static CalculateRequest Wealthy(decimal cash, decimal investments, decimal totalDebt) =>
        Scoring.Profile(30000, 29000, payment: 0, debt: totalDebt, cash: cash, investments: investments, impatience: 5);

    public static TheoryData<string> OldLines() => new() { "VERY_HIGH_INCOME", "VERY_HIGH_WEALTH", "EXTREME_DEBT" };

    [Theory]
    [MemberData(nameof(OldLines))]
    public void OneTlAcrossAnOldV2Line_MovesTheScoreByAtMostOnePoint(string v2Rule)
    {
        var (below, at) = v2Rule switch
        {
            // monthly income 999,999 vs 1,000,000 (v2: the step to 100)
            "VERY_HIGH_INCOME" => (NoReserve(999_999), NoReserve(1_000_000)),
            // net worth 9,999,999 vs 10,000,000: one TL less debt (v2: the step to 100)
            "VERY_HIGH_WEALTH" => (Wealthy(2_000_000, 9_000_000, 1_000_001), Wealthy(2_000_000, 9_000_000, 1_000_000)),
            // net debt 99,999,999 vs 100,000,000 (v2: 75 -> 0, audit G1c)
            _ => (HealthyRatios(100_095_999), HealthyRatios(100_096_000))
        };

        var (scoreBelow, scoreAt) = (Scoring.Score(below).Score, Scoring.Score(at).Score);

        Assert.True(Math.Abs(scoreAt - scoreBelow) <= 1, $"{v2Rule}: {scoreBelow} -> {scoreAt}");
    }

    [Fact]
    public void VeryHighIncome_WithoutCash_IsScoredByTheRatios()
    {
        // v2: 100 (VERY_HIGH_INCOME). v3: no reserve yet and 10% savings -> the demo richincome, 53 MEDIUM
        var result = Scoring.Score(NoReserve(1_000_000));

        Assert.Equal((53, "MEDIUM"), (result.Score, result.Segment));
        Assert.Null(result.AppliedRule);
        Assert.Contains("Low cash reserve", result.Warnings);
    }

    [Fact]
    public void AHighIncome_DoesNotHideOverspending()
    {
        // audit G2: income 1,000,000 but expenses 2,000,000 gave 100 in v2 (the rule ignored the cash flow)
        var result = Scoring.Score(Scoring.Profile(1_000_000, 2_000_000));

        Assert.Equal((38, "LOW"), (result.Score, result.Segment));
        Assert.Contains("Negative savings rate", result.Warnings);
    }

    [Fact]
    public void AmountsAreNotCapped_HugeIncomeStillScores_ByTheSameRatios()
    {
        // the advisor's test: a very large salary is accepted, not rejected or cut off; with no TL threshold the same
        // ratios give the same score at any size
        var huge = Scoring.Score(NoReserve(50_000_000_000m));

        Assert.Equal(Scoring.Score(NoReserve(1_000_000)).Json, huge.Json);
    }

    [Fact]
    public void ExtremeNetDebt_ScoresZero_ByTheSolvencyCap()
    {
        // net debt ~2,500 years of income: the cap (0 from 15 years) takes every point
        var result = Scoring.Score(HealthyRatios(100_096_000));

        Assert.Equal((0, "LOW"), (result.Score, result.Segment));
        Assert.Equal(ScoringRules.SolvencyCapRule, result.AppliedRule);
        Assert.Equal(0, result.Factors.Sum(f => f.Value));
        Assert.Contains("Extreme total debt", result.Warnings);
        // the true reasons stay in the list, the cap only adds its own
        Assert.Contains("High total debt", result.Warnings);
    }

    [Fact]
    public void DebtOf104YearsOfIncome_IsNoLongerHigh()
    {
        // audit G3: 50,000,000 owed on 40,000 a month scored 75 HIGH in v2 (the debt factor could lose only 25 points)
        var result = Scoring.Score(HealthyRatios(50_000_000));

        Assert.Equal(0, result.Score);
        Assert.Equal(ScoringRules.SolvencyCapRule, result.AppliedRule);
    }

    [Fact]
    public void TheSolvencyCap_LowersTheScoreStepByStep()
    {
        // net debt from 4 to 16 years of income: the score falls, never jumps, and is 0 from 15 years on
        int? last = null;
        for (var years = 4; years <= 16; years++)
        {
            var result = Scoring.Score(Scoring.Profile(40000, 16000, 12000, 480000m * years, 0, 0, 1));

            Assert.Equal(years > 5 ? ScoringRules.SolvencyCapRule : null, result.AppliedRule);
            if (last is { } previous)
            {
                Assert.True(result.Score <= previous, $"{years} years: {result.Score} > {previous}");
                Assert.True(previous - result.Score <= 12, $"{years} years: fell from {previous} to {result.Score}");
            }
            last = result.Score;
        }

        Assert.Equal(0, last);
    }

    [Fact]
    public void LargeDebtCoveredByLiquidAssets_IsNotCapped()
    {
        // 150,000,000 owed but 500,000,000 invested (250,000,000 liquid): no net debt, nothing to cap
        var result = Scoring.Score(HealthyRatios(150_000_000, investments: 500_000_000));

        Assert.Equal(100, result.Score);
        // the runway is long, but the score is already 100 without it -> no label
        Assert.Null(result.AppliedRule);
        Assert.Empty(result.Warnings);
    }

    [Fact]
    public void WealthRunway_LiftsTheCashFlowFactors()
    {
        // demo richwealth: 30,000 a month, spends 29,000, but 6,500,000 liquid against 1,000,000 debt = 15.8 years
        // of expenses -> runway share 0.63: the savings factor gets 19 instead of 10
        var result = Scoring.Score(Wealthy(2_000_000, 9_000_000, 1_000_000));

        Assert.Equal((84, "HIGH"), (result.Score, result.Segment));
        Assert.Equal(ScoringRules.WealthRunwayRule, result.AppliedRule);
        Assert.Equal(19, result.Factor("SavingsRate"));
        Assert.Equal(["High impatience"], result.Warnings);
    }

    [Fact]
    public void AShortRunway_LiftsTheScore_ButGetsNoLabel()
    {
        // golden case L1: 100,000 cash = 0.42 years of expenses. The lift (share 0.017) rounds the savings factor up
        // to 1 point (score 26 instead of 25), but a few months of cash are no "wealth runway" -> no label
        var result = Scoring.Score(Scoring.Profile(30000, 20000, 30000, 0, 100000, 0, 3));
        var measures = FinancialIqCommandManager.Measure(Scoring.Profile(30000, 20000, 30000, 0, 100000, 0, 3));

        Assert.True(measures.RunwayYears < ScoringRules.WealthRunwayLabelMinYears);
        Assert.Equal(1, result.Factor("SavingsRate"));
        Assert.Equal((26, "LOW"), (result.Score, result.Segment));
        Assert.Null(result.AppliedRule);
    }

    [Fact]
    public void ALongRunway_GetsTheLabel()
    {
        // golden case L2: spends 33,000 on 30,000 a month, but 11,880,000 cash = 30 years of expenses -> full lift:
        // savings 30 instead of 0, score 98 instead of 68
        var result = Scoring.Score(Scoring.Profile(30000, 33000, 0, 0, 11_880_000, 0, 3));

        Assert.Equal(30, result.Factor("SavingsRate"));
        Assert.Equal((98, "HIGH"), (result.Score, result.Segment));
        Assert.Equal(ScoringRules.WealthRunwayRule, result.AppliedRule);
        Assert.Empty(result.Warnings);
    }

    [Fact]
    public void TheLabel_StartsAtExactlyFiveYearsOfRunway()
    {
        // 12 x 33,000 = 396,000 a year: 1,980,000 = 5 years (share 0.2, savings 6 instead of 0) -> label;
        // 1 TL less is just under 5 years -> no label, and the score moves by at most 1
        var atFive = Scoring.Score(Scoring.Profile(30000, 33000, 0, 0, 1_980_000, 0, 3));
        var below = Scoring.Score(Scoring.Profile(30000, 33000, 0, 0, 1_979_999, 0, 3));

        Assert.Equal(ScoringRules.WealthRunwayRule, atFive.AppliedRule);
        Assert.Equal(6, atFive.Factor("SavingsRate"));
        Assert.Null(below.AppliedRule);
        Assert.True(Math.Abs(atFive.Score - below.Score) <= 1);
    }

    [Fact]
    public void DebtCountsAgainstTheWealth()
    {
        var lessDebt = Scoring.Score(Wealthy(3_000_000, 9_000_000, 1_000_000));
        var moreDebt = Scoring.Score(Wealthy(3_000_000, 9_000_000, 5_000_000));

        Assert.True(moreDebt.Score < lessDebt.Score, $"{moreDebt.Score} >= {lessDebt.Score}");
    }

    [Fact]
    public void BorrowingToHoldCash_DoesNotLengthenTheRunway()
    {
        // 1,000,000 more cash bought with 1,000,000 more debt: the liquid net worth, and so the runway, is the same
        var before = FinancialIqCommandManager.Measure(Wealthy(2_000_000, 9_000_000, 1_000_000));
        var after = FinancialIqCommandManager.Measure(Wealthy(3_000_000, 9_000_000, 2_000_000));

        Assert.Equal(before.RunwayYears, after.RunwayYears);
        Assert.Equal(before.RunwayShare, after.RunwayShare);
    }

    [Fact]
    public void OlderCallersWithoutTotalDebt_AreScored_AndTheInstallmentIsFlagged()
    {
        // same numbers as the sample weak profile but without TotalDebt (defaults to 0): an installment without any
        // debt is flagged as a data-quality warning, never rejected
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 30000,
            MonthlyExpenses = 25000,
            MonthlyDebtPayment = 7000,
            CashReserve = 3000,
            ImpatienceLevel = 5
        };

        var result = Scoring.Score(request);

        Assert.Equal(26, result.Score);
        Assert.Null(result.AppliedRule);
        Assert.Equal("Installment without debt", result.Warnings[^1]);
    }
}
