using System.Linq.Expressions;
using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Infrastructure.Abstract;

namespace FinancialIQ.Tests;

// input checks of CalculateAsync (the part before scoring); the database is an in-memory fake
public class CalculateValidationTests
{
    private readonly FakeResultDal _dal = new();
    private FinancialIqCommandManager Manager => new(_dal);

    private static CalculateRequest Request(string userId) => new()
    {
        UserId = userId,
        MonthlyIncome = 10000,
        MonthlyExpenses = 4000,
        MonthlyDebtPayment = 1000,
        CashReserve = 24000
    };

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task BlankUserId_IsRejected_AndNothingIsStored(string userId)
    {
        var result = await Manager.CalculateAsync(Request(userId));

        Assert.False(result.Success);
        Assert.Equal(Messages.InvalidUserId, result.Message);
        Assert.Empty(_dal.Stored);
    }

    [Fact]
    public async Task UserIdLongerThan100_IsRejected()
    {
        var result = await Manager.CalculateAsync(Request(new string('a', 101)));

        Assert.Equal(Messages.InvalidUserId, result.Message);
        Assert.Empty(_dal.Stored);
    }

    [Fact]
    public async Task ValidRequest_IsScoredAndStored()
    {
        var result = await Manager.CalculateAsync(Request("u1"));

        Assert.True(result.Success);
        Assert.Equal("u1", Assert.Single(_dal.Stored).UserId);
        // v3: reserve 4.8 months 25 + installment 10% 25 + no debt 10 + savings 50% 30 + impatience 3 -> 3
        Assert.Equal(93, result.Data!.Score);
        // since contract v2 the breakdown is a JSON object in the response, not a string
        Assert.Equal(System.Text.Json.JsonValueKind.Object, result.Data.FactorBreakdown.ValueKind);
        Assert.Equal("v3", result.Data.FactorBreakdown.GetProperty("version").GetString());
        Assert.Equal(System.Text.Json.JsonValueKind.Object, result.Data.FactorBreakdown.GetProperty("factorMaximums").ValueKind);
    }

    [Fact]
    public async Task StoredResult_SaysWhichScoringVersionProducedIt()
    {
        await Manager.CalculateAsync(Request("u1"));

        // the procedure writes it into financial_iq_results and iq_history (foreign key to scoring_rule_versions)
        Assert.Equal(ScoringRules.ScoringVersion, Assert.Single(_dal.Stored).ScoringVersion);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-1)]
    public async Task IncomeNotAboveZero_IsStillRejected(decimal income)
    {
        // v3 divides by the income (and its expense floor is a share of it), so the v2 rule stays: income > 0
        var request = Request("u1");
        request.MonthlyIncome = income;

        var result = await Manager.CalculateAsync(request);

        Assert.Equal(Messages.InvalidMonthlyIncome, result.Message);
        Assert.Empty(_dal.Stored);
    }

    [Fact]
    public async Task NegativeTotalDebt_IsRejected_AndNothingIsStored()
    {
        var request = Request("u1");
        request.TotalDebt = -1;

        var result = await Manager.CalculateAsync(request);

        Assert.Equal(Messages.NegativeAmountNotAllowed, result.Message);
        Assert.Empty(_dal.Stored);
    }

    [Fact]
    public async Task NegativeInvestmentAmount_IsRejected_AndNothingIsStored()
    {
        var request = Request("u1");
        request.InvestmentAmount = -1;

        var result = await Manager.CalculateAsync(request);

        Assert.Equal(Messages.NegativeAmountNotAllowed, result.Message);
        Assert.Empty(_dal.Stored);
    }

    private sealed class FakeResultDal : IFinancialIqResultDal
    {
        public List<FinancialIqResult> Stored { get; } = new();

        public Task SaveAsync(FinancialIqResult entity)
        {
            Stored.RemoveAll(r => r.UserId == entity.UserId);
            Stored.Add(entity);
            return Task.CompletedTask;
        }

        public Task<FinancialIqResult?> GetAsync(Expression<Func<FinancialIqResult, bool>> filter)
            => Task.FromResult(Stored.AsQueryable().FirstOrDefault(filter));

        public Task<List<FinancialIqResult>> GetAllAsync(Expression<Func<FinancialIqResult, bool>>? filter = null)
            => Task.FromResult(filter == null ? Stored.ToList() : Stored.AsQueryable().Where(filter).ToList());

        public Task AddAsync(FinancialIqResult entity) => throw new NotSupportedException();
        public Task UpdateAsync(FinancialIqResult entity) => throw new NotSupportedException();
        public Task DeleteAsync(FinancialIqResult entity) => throw new NotSupportedException();
    }
}
