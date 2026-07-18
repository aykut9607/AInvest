using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;
using Xunit;

namespace FinancialIQ.Tests;

public class FinancialIqManagerTests
{
    [Fact]
    public void Balanced_ShouldReturnBalancedSegment()
    {
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 50000,
            MonthlyExpenses = 30000,
            MonthlyDebtPayment = 8000,
            CashReserve = 60000
        };

        var (score, segment) = FinancialIqManager.CalculateScore(request);

        Assert.Equal("BALANCED", segment);
    }


   [Fact]
public void HighDebt_ShouldReturnHighRiskSegment()
{
    var request = new CalculateRequest
    {
        UserId = "test-user",
        MonthlyIncome = 50000,
        MonthlyExpenses = 42000,
        MonthlyDebtPayment = 22000,
        CashReserve = 5000
    };

    var (score, segment) = FinancialIqManager.CalculateScore(request);

    Assert.Equal("HIGH_RISK", segment);
}


    [Fact]
    public void LowCashReserve_ShouldReturnLowScoreForCashFactor()
    {
        var request = new CalculateRequest
        {
            UserId = "test-user",
            MonthlyIncome = 60000,
            MonthlyExpenses = 20000,
            MonthlyDebtPayment = 5000,
            CashReserve = 5000   // 5000/20000 = 0.25 ay — 1 aydan az
        };

        var (score, segment) = FinancialIqManager.CalculateScore(request);

        // toplam skoru değil, sadece bu senaryonun mantıklı bir segmentte olduğunu doğruluyoruz
        Assert.NotEqual("STRONG", segment);
    }


 [Fact]
public void ZeroExpenses_ShouldNotThrow()
{
    var request = new CalculateRequest
    {
        UserId = "test-user",
        MonthlyIncome = 40000,
        MonthlyExpenses = 0,
        MonthlyDebtPayment = 0,
        CashReserve = 30000
    };

    var exception = Record.Exception(() => FinancialIqManager.CalculateScore(request));

    Assert.Null(exception);
}
}