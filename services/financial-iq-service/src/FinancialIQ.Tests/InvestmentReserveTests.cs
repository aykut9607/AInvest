using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;
using System.Text.Json;
using Xunit;

namespace FinancialIQ.Tests;

// factor 1 counts half of the investments as reserve (ScoringRules.InvestmentReserveShare)
public class InvestmentReserveTests
{
    // income 20,000, expenses 10,000 a month, debt payment 1,000 (5%), savings 45%
    private static CalculateRequest Profile(decimal cash, decimal investments) => new()
    {
        UserId = "test-user",
        MonthlyIncome = 20000,
        MonthlyExpenses = 10000,
        MonthlyDebtPayment = 1000,
        CashReserve = cash,
        InvestmentAmount = investments,
        ImpatienceLevel = 1
    };

    private static JsonElement Breakdown(CalculateRequest request)
    {
        var (_, _, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);
        return JsonDocument.Parse(factorBreakdown).RootElement.Clone();
    }

    private static int ReservePoints(CalculateRequest request) =>
        Breakdown(request).GetProperty("factors").GetProperty("CashReserveMonths").GetInt32();

    [Fact]
    public void NoInvestments_ScoresTheSameAsBefore()
    {
        // 30,000 cash / 10,000 expenses = 3 months -> 15 points, as without the investment rule
        Assert.Equal(15, ReservePoints(Profile(cash: 30000, investments: 0)));
    }

    [Fact]
    public void HalfOfTheInvestmentsCountsAsReserve()
    {
        // 120,000 invested * 0.5 = 60,000 = 6 months of expenses -> full 25 points
        Assert.Equal(25, ReservePoints(Profile(cash: 0, investments: 120000)));
    }

    [Fact]
    public void InvestmentsDoNotCountInFull()
    {
        // 119,998 * 0.5 = 59,999 -> just under 6 months -> 15 points (in full they would be ~12 months)
        Assert.Equal(15, ReservePoints(Profile(cash: 0, investments: 119998)));
    }

    [Fact]
    public void CashAndInvestmentsAddUp()
    {
        // 40,000 cash + 40,000 * 0.5 = 60,000 -> 6 months
        Assert.Equal(25, ReservePoints(Profile(cash: 40000, investments: 40000)));
    }

    [Fact]
    public void InvestmentsRemoveTheLowReserveWarning()
    {
        // without the investments the reserve is 0 months -> "Low cash reserve"
        var withoutInvestments = Breakdown(Profile(cash: 0, investments: 0));
        var withInvestments = Breakdown(Profile(cash: 0, investments: 120000));

        Assert.Contains("Low cash reserve", withoutInvestments.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()));
        Assert.DoesNotContain("Low cash reserve", withInvestments.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()));
    }

    [Fact]
    public void DocumentedSampleProfile_Scores8()
    {
        // the sample profile in the docs (CLAUDE.md 6.7): 3,000 cash + 10,000 * 0.5 = 8,000 / 25,000 = 0.32 months -> 0 points;
        // installment 23% -> 8, savings negative -> 0, expenses 83% -> 0, impatience 5 -> 0. v1 gave 6 (with the risk factor)
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 30000,
            MonthlyExpenses = 25000,
            MonthlyDebtPayment = 7000,
            CashReserve = 3000,
            TotalDebt = 90000,
            InvestmentAmount = 10000,
            ImpatienceLevel = 5
        };

        var (score, segment, _) = FinancialIqCommandManager.CalculateScore(request);

        Assert.Equal(8, score);
        Assert.Equal("LOW", segment);
    }
}
