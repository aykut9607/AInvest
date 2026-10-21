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
    private FinancialIqManager Manager => new(_dal);

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
        Assert.Equal(88, result.Data!.Score);
    }

    [Fact]
    public async Task InvalidRiskPreference_IsRejected()
    {
        var request = Request("u1");
        request.RiskPreference = "high";

        var result = await Manager.CalculateAsync(request);

        Assert.Equal(Messages.InvalidRiskPreference, result.Message);
    }

    private sealed class FakeResultDal : IFinancialIqResultDal
    {
        public List<FinancialIqResult> Stored { get; } = new();

        public Task UpsertAsync(FinancialIqResult entity)
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
