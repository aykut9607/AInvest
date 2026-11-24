using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Tests;

// rules around the payoff schedule; the schedule itself is computed by dbo.fn_DebtPayoffSchedule in SQL Server
// (checked end to end against the closed-form loan formula, see CLAUDE.md 5.4), here the database is a fake
public class DebtPayoffTests
{
    private readonly FakeReadDal _readDal = new();
    private FinancialIqQueryManager Manager => new(_readDal);

    [Fact]
    public async Task WithoutARate_TheDefaultRateIsUsed()
    {
        _readDal.Schedule.Add(new DebtPayoffMonth { Month = 1, Interest = 35, Payment = 1035, ClosingBalance = 0 });

        var result = await Manager.GetDebtPayoffAsync(new DebtPayoffRequest { TotalDebt = 1000, MonthlyPayment = 2000 });

        Assert.True(result.Success);
        Assert.Equal(DebtPayoffRules.DefaultMonthlyInterestRate, result.Data!.MonthlyInterestRate);
        Assert.Equal(DebtPayoffRules.DefaultMonthlyInterestRate, _readDal.LastRequestedRate);
    }

    [Fact]
    public async Task TheCallersRate_IsUsed_IncludingZero()
    {
        _readDal.Schedule.Add(new DebtPayoffMonth { Month = 1, Interest = 0, Payment = 1000, ClosingBalance = 0 });

        // interest-free installments are common, 0 must be accepted
        var result = await Manager.GetDebtPayoffAsync(new DebtPayoffRequest { TotalDebt = 1000, MonthlyPayment = 1000, MonthlyInterestRate = 0 });

        Assert.True(result.Success);
        Assert.Equal(0, _readDal.LastRequestedRate);
    }

    [Fact]
    public async Task PaidOffSchedule_GivesMonthsAndTotals()
    {
        _readDal.Schedule.AddRange([
            new DebtPayoffMonth { Month = 1, OpeningBalance = 2000, Interest = 70, Payment = 1500, ClosingBalance = 570 },
            new DebtPayoffMonth { Month = 2, OpeningBalance = 570, Interest = 19.95m, Payment = 589.95m, ClosingBalance = 0 }
        ]);

        var result = await Manager.GetDebtPayoffAsync(new DebtPayoffRequest { TotalDebt = 2000, MonthlyPayment = 1500 });

        Assert.True(result.Data!.PaidOff);
        Assert.Equal(2, result.Data.Months);
        Assert.Equal(89.95m, result.Data.TotalInterest);
        Assert.Equal(2089.95m, result.Data.TotalPaid);
        Assert.Equal(2, result.Data.Schedule.Count);
    }

    [Fact]
    public async Task PaymentNotCoveringTheInterest_IsNeverPaidOff_AndTheDatabaseIsNotAsked()
    {
        // 100,000 x 3.5% = 3,500 interest in the first month; 3,500 pays only the interest
        var result = await Manager.GetDebtPayoffAsync(new DebtPayoffRequest { TotalDebt = 100000, MonthlyPayment = 3500 });

        Assert.True(result.Success);
        Assert.False(result.Data!.PaidOff);
        Assert.Null(result.Data.Months);
        Assert.Equal(Messages.PaymentDoesNotCoverInterest, result.Message);
        Assert.Null(_readDal.LastRequestedRate);
    }

    [Fact]
    public async Task ScheduleThatHitsTheMonthLimit_IsNotPaidOff()
    {
        _readDal.Schedule.Add(new DebtPayoffMonth { Month = 600, ClosingBalance = 12.5m });

        var result = await Manager.GetDebtPayoffAsync(new DebtPayoffRequest { TotalDebt = 100000, MonthlyPayment = 3501 });

        Assert.False(result.Data!.PaidOff);
        Assert.Null(result.Data.Months);
        Assert.Equal(Messages.DebtNotPaidOffWithinLimit, result.Message);
    }

    [Fact]
    public async Task NoDebt_IsPaidOffInZeroMonths()
    {
        var result = await Manager.GetDebtPayoffAsync(new DebtPayoffRequest { TotalDebt = 0, MonthlyPayment = 0 });

        Assert.True(result.Data!.PaidOff);
        Assert.Equal(0, result.Data.Months);
        Assert.Null(_readDal.LastRequestedRate);
    }

    [Theory]
    [InlineData(-1, 100, null, Messages.NegativeAmountNotAllowed)]
    [InlineData(100, -1, null, Messages.NegativeAmountNotAllowed)]
    [InlineData(1_000_000_000_000_000, 100, null, Messages.AmountTooLarge)]
    [InlineData(1000, 100, -0.01, Messages.InvalidMonthlyInterestRate)]
    [InlineData(1000, 100, 1.5, Messages.InvalidMonthlyInterestRate)]
    public async Task InvalidInput_IsRejected(double debt, double payment, double? rate, string expectedMessage)
    {
        var result = await Manager.GetDebtPayoffAsync(new DebtPayoffRequest
        {
            TotalDebt = (decimal)debt,
            MonthlyPayment = (decimal)payment,
            MonthlyInterestRate = (decimal?)rate
        });

        Assert.False(result.Success);
        Assert.Equal(expectedMessage, result.Message);
    }
}
