using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Tests;

// properties scoring v3 promises for EVERY profile, checked on a fixed sample of ~450 (SampleProfiles):
// the factors add up to the score, a better input never lowers it, 1 TL never moves it by more than 1 point,
// the score does not depend on the price level, and a warning appears exactly when a factor is weak
public class ScoringPropertyTests
{
    private static readonly string[] FactorOrder = ["CashReserveMonths", "InstallmentToIncome", "NetDebtToIncome", "SavingsRate", "Impatience"];

    // which warnings explain a weak factor
    private static readonly Dictionary<string, string[]> FactorWarnings = new()
    {
        ["CashReserveMonths"] = ["Low cash reserve"],
        ["InstallmentToIncome"] = ["High debt burden", "Elevated debt burden"],
        ["NetDebtToIncome"] = ["High total debt", "Elevated total debt"],
        ["SavingsRate"] = ["Negative savings rate", "Low savings rate"],
        ["Impatience"] = ["High impatience"]
    };

    private static readonly HashSet<string> KnownWarnings =
    [
        .. FactorWarnings.Values.SelectMany(w => w),
        "Extreme total debt", "Installment below interest", "Expenses look too low", "Installment without debt", "Installment exceeds total debt"
    ];

    [Fact]
    public void FactorsAddUpToTheScore_AndStayWithinTheirMaximums()
    {
        foreach (var profile in SampleProfiles.All)
        {
            var result = Scoring.Score(profile);
            var maximums = result.FactorMaximums.ToDictionary(p => p.Key, p => p.Value);

            Assert.Equal(result.Score, result.Factors.Sum(f => f.Value));
            Assert.Equal(FactorOrder, result.Factors.Select(f => f.Key));
            Assert.Equal(FactorOrder, result.FactorMaximums.Select(f => f.Key));
            Assert.Equal(100, maximums.Values.Sum());
            foreach (var (name, points) in result.Factors)
                Assert.True(points >= 0 && points <= maximums[name], $"{profile.UserId}: {name} = {points}");
            Assert.InRange(result.Score, 0, 100);
            Assert.Equal(result.Score >= 71 ? "HIGH" : result.Score >= 41 ? "MEDIUM" : "LOW", result.Segment);
            Assert.Equal(ScoringRules.ScoringVersion, result.Breakdown.GetProperty("version").GetString());
        }
    }

    // income, cash and investments up / expenses, installment and debt down / impatience down = favourable
    private static readonly HashSet<string> BetterWhenHigher =
        [nameof(CalculateRequest.MonthlyIncome), nameof(CalculateRequest.CashReserve), nameof(CalculateRequest.InvestmentAmount)];

    [Fact]
    public void AFavourableChangeOfOneInput_NeverLowersTheScore_AndAnUnfavourableOneNeverRaisesIt()
    {
        var checks = 0;
        foreach (var original in SampleProfiles.All)
        {
            foreach (var field in Scoring.MoneyFields)
            {
                // a zero input is moved away from 0 first so both directions exist
                var profile = Scoring.Get(original, field) == 0 ? Scoring.With(original, field, 1000m) : original;
                var value = Scoring.Get(profile, field);
                foreach (var (changed, favourable) in new[] { (Math.Round(value * 1.3m, 2), BetterWhenHigher.Contains(field)), (Math.Round(value * 0.7m, 2), !BetterWhenHigher.Contains(field)) })
                {
                    AssertDirection(profile, Scoring.With(profile, field, changed), favourable, $"{field} {value} -> {changed}");
                    checks++;
                }
            }

            foreach (var (level, favourable) in new[] { (original.ImpatienceLevel - 1, true), (original.ImpatienceLevel + 1, false) })
            {
                if (level is < 1 or > 5) continue;
                AssertDirection(original, Scoring.With(original, nameof(CalculateRequest.ImpatienceLevel), level), favourable, $"impatience -> {level}");
                checks++;
            }
        }

        Assert.True(checks > 4000, $"only {checks} checks ran");
    }

    // 26 Nov fix: the reserve used to be measured in max(expenses, 10% of the income), so with tiny expenses a higher
    // income meant fewer reserve months: income 100,000 -> 200,000 (expenses 5,000, cash 60,000) scored 100 -> 88
    [Fact]
    public void MoreIncome_NeverLowersTheScore_EvenWhenTheExpensesAreBelowTenPercentOfIt()
    {
        var before = Scoring.Profile(100_000m, 5_000m, cash: 60_000m, impatience: 1);
        var after = Scoring.With(before, nameof(CalculateRequest.MonthlyIncome), 200_000m);

        Assert.Equal(100, Scoring.Score(before).Score);
        Assert.Equal(100, Scoring.Score(after).Score);

        decimal[] incomes = [1_000m, 5_000m, 10_000m, 20_000m, 50_000m, 100_000m, 200_000m, 500_000m, 1_000_000m, 5_000_000m];
        foreach (var expenses in new[] { 0m, 500m, 2_000m, 5_000m })
        foreach (var (payment, debt) in new[] { (0m, 0m), (5_000m, 100_000m) })
        foreach (var cash in new[] { 0m, 30_000m, 1_000_000m })
        {
            var previous = -1;
            foreach (var income in incomes)
            {
                var score = Scoring.Score(Scoring.Profile(income, expenses, payment, debt, cash, impatience: 1)).Score;
                Assert.True(score >= previous, $"expenses {expenses}, payment {payment}, cash {cash}: income {income} scored {score} < {previous}");
                previous = score;
            }
        }
    }

    private static void AssertDirection(CalculateRequest before, CalculateRequest after, bool favourable, string change)
    {
        var (b, a) = (Scoring.Score(before).Score, Scoring.Score(after).Score);
        if (favourable) Assert.True(a >= b, $"{before.UserId}: {change} lowered the score {b} -> {a}");
        else Assert.True(a <= b, $"{before.UserId}: {change} raised the score {b} -> {a}");
    }

    [Fact]
    public void TheSameFinancesAtHigherPrices_ScoreExactlyTheSame()
    {
        // no TL threshold anywhere: every amount x 1.3 (inflation) gives the same breakdown, character for character.
        // The one TL number is the 2,000 TL data-quality floor of the reserve expenses, so expenses below it are skipped
        foreach (var p in SampleProfiles.All.Where(p => p.MonthlyExpenses >= ScoringRules.ExpenseFloorTl))
        {
            var inflated = Scoring.Profile(p.MonthlyIncome * 1.3m, p.MonthlyExpenses * 1.3m, p.MonthlyDebtPayment * 1.3m,
                p.TotalDebt * 1.3m, p.CashReserve * 1.3m, p.InvestmentAmount * 1.3m, p.ImpatienceLevel);

            Assert.True(Scoring.Score(p).Json == Scoring.Score(inflated).Json, $"{p.UserId}: the breakdown changed at 1.3x prices");
        }
    }

    // a profile sitting exactly on one anchor of a scale (or on an old v2 line), and the same profile 1 TL away
    public static TheoryData<string> AnchorProbeNames()
    {
        var data = new TheoryData<string>();
        foreach (var name in AnchorProbes.Keys) data.Add(name);
        return data;
    }

    // base: income 40,000, expenses 16,000, installment 2,000, debt 10,000, cash 64,000, impatience 2
    private static CalculateRequest Base(decimal? expenses = null, decimal? payment = null, decimal? debt = null, decimal? cash = null) =>
        Scoring.Profile(40000, expenses ?? 16000, payment ?? 2000, debt ?? 10000, cash ?? 64000, 0, 2);

    private static readonly Dictionary<string, (CalculateRequest At, string Field, decimal Delta)> AnchorProbes = new()
    {
        // reserve months = cash / 18,000 (outflow)
        ["reserve 0 months"] = (Base(cash: 0), nameof(CalculateRequest.CashReserve), +1),
        ["reserve 3 months"] = (Base(cash: 54000), nameof(CalculateRequest.CashReserve), -1),
        ["reserve 6 months"] = (Base(cash: 108000), nameof(CalculateRequest.CashReserve), -1),
        // installment / income (debt 12 installments, so the interest floor does not bind)
        ["installment 10%"] = (Base(payment: 4000, debt: 48000), nameof(CalculateRequest.MonthlyDebtPayment), +1),
        ["installment 20%"] = (Base(payment: 8000, debt: 96000), nameof(CalculateRequest.MonthlyDebtPayment), +1),
        ["installment 36%"] = (Base(payment: 14400, debt: 288000), nameof(CalculateRequest.MonthlyDebtPayment), +1),
        ["installment 50%"] = (Base(payment: 20000, debt: 240000), nameof(CalculateRequest.MonthlyDebtPayment), +1),
        // net debt in years of income (480,000 a year), no cash
        ["net debt 0.5 years"] = (Base(payment: 9000, debt: 240000, cash: 0), nameof(CalculateRequest.TotalDebt), +1),
        ["net debt 1 year"] = (Base(payment: 17000, debt: 480000, cash: 0), nameof(CalculateRequest.TotalDebt), +1),
        ["net debt 3 years"] = (Base(debt: 1440000, cash: 0), nameof(CalculateRequest.TotalDebt), +1),
        ["solvency cap starts (5 years)"] = (Base(payment: 12000, debt: 2400000, cash: 0), nameof(CalculateRequest.TotalDebt), +1),
        ["solvency cap ends (15 years)"] = (Base(payment: 12000, debt: 7200000, cash: 0), nameof(CalculateRequest.TotalDebt), +1),
        // savings rate = (38,000 - expenses) / 40,000
        ["savings -10%"] = (Base(expenses: 42000), nameof(CalculateRequest.MonthlyExpenses), +1),
        ["savings 0%"] = (Base(expenses: 38000), nameof(CalculateRequest.MonthlyExpenses), +1),
        ["savings 10%"] = (Base(expenses: 34000), nameof(CalculateRequest.MonthlyExpenses), +1),
        ["savings 20%"] = (Base(expenses: 30000), nameof(CalculateRequest.MonthlyExpenses), +1),
        // the floors
        ["expense floor (10% of income)"] = (Base(expenses: 4000), nameof(CalculateRequest.MonthlyExpenses), -1),
        ["interest floor (3.5% of net debt)"] = (Base(payment: 3500, debt: 100000, cash: 0), nameof(CalculateRequest.MonthlyDebtPayment), -1),
        // the excess over the 6-month target starts to offset the debt (outflow 16,000 + 18,000, 6 x 34,000 = 204,000)
        ["debt offset starts"] = (Base(debt: 500000, payment: 18000, cash: 204000), nameof(CalculateRequest.CashReserve), +1),
        // wealth runway: liquid net worth / 192,000 (12 x 16,000)
        ["runway 0 years"] = (Base(cash: 10000), nameof(CalculateRequest.CashReserve), +1),
        ["runway 25 years"] = (Base(cash: 4810000), nameof(CalculateRequest.CashReserve), -1),
        // the three v2 TL rules (were cliffs of 75 to 100 points)
        ["v2 VERY_HIGH_INCOME line"] = (Scoring.Profile(999999, 900000, 0, 0, 0, 0, 5), nameof(CalculateRequest.MonthlyIncome), +1),
        ["v2 VERY_HIGH_WEALTH line"] = (Scoring.Profile(30000, 29000, 0, 1000000, 2000000, 9000000, 5), nameof(CalculateRequest.TotalDebt), +1),
        ["v2 EXTREME_DEBT line"] = (Scoring.Profile(40000, 16000, 4000, 100095999, 96000, 0, 1), nameof(CalculateRequest.TotalDebt), +1)
    };

    [Theory]
    [MemberData(nameof(AnchorProbeNames))]
    public void OneTl_AtAnAnchor_MovesTheScoreByAtMostOnePoint(string probe)
    {
        var (at, field, delta) = AnchorProbes[probe];
        var moved = Scoring.With(at, field, Scoring.Get(at, field) + delta);

        var (before, after) = (Scoring.Score(at).Score, Scoring.Score(moved).Score);

        Assert.True(Math.Abs(after - before) <= 1, $"{probe}: {before} -> {after}");
    }

    [Fact]
    public void OneTl_InTheGoldenTablePairs_MovesTheScoreByAtMostOnePoint()
    {
        // "X" and "X+" differ by 1 TL in one input; G4+ is a different test (borrowing to hold cash), not a 1 TL step
        foreach (var plus in GoldenTable.Cases.Where(c => c.Id.EndsWith('+') && c.Id != "G4+"))
        {
            var at = GoldenTable.Get(plus.Id.TrimEnd('+'));
            Assert.True(Math.Abs(plus.Score - Scoring.Score(at.Request).Score) <= 1, plus.Id);
            Assert.True(Math.Abs(Scoring.Score(plus.Request).Score - Scoring.Score(at.Request).Score) <= 1, plus.Id);
        }
    }

    [Fact]
    public void AWarning_AppearsExactlyWhenAFactorIsBelow60PercentOfItsMaximum()
    {
        foreach (var profile in SampleProfiles.All)
        {
            var result = Scoring.Score(profile);
            var warnings = result.Warnings;

            Assert.Equal(warnings.Length, warnings.Distinct().Count());
            Assert.All(warnings, w => Assert.Contains(w, KnownWarnings));

            if (result.AppliedRule == ScoringRules.SolvencyCapRule)
            {
                // the cap scales the points down; its warning explains what it took (the factor warnings are judged
                // on the points before the cap, which the breakdown does not show)
                Assert.Contains("Extreme total debt", warnings);
                continue;
            }

            Assert.DoesNotContain("Extreme total debt", warnings);
            foreach (var (name, points) in result.Factors)
            {
                var weak = points < result.FactorMaximums.Single(m => m.Key == name).Value * 0.6m;
                Assert.True(weak == warnings.Intersect(FactorWarnings[name]).Any(),
                    $"{profile.UserId}: {name} = {points}, warnings [{string.Join(", ", warnings)}]");
            }
        }
    }

    [Fact]
    public void AProfileWithoutWarnings_ScoresAtLeast60()
    {
        // follows from the rule above: without a warning every factor keeps at least 60% of its maximum
        foreach (var profile in SampleProfiles.All)
        {
            var result = Scoring.Score(profile);
            if (result.Warnings.Length == 0) Assert.True(result.Score >= 60, $"{profile.UserId}: {result.Score}");
        }
    }

    [Fact]
    public void TheSampleReachesTheCapAndTheRunway()
    {
        // the properties above are only meaningful if the sample covers the two mechanisms
        var rules = SampleProfiles.All.Select(p => Scoring.Score(p).AppliedRule).ToList();

        Assert.Contains(ScoringRules.SolvencyCapRule, rules);
        Assert.Contains(ScoringRules.WealthRunwayRule, rules);
        Assert.Contains(null, rules);
    }
}
