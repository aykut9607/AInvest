using System.Linq.Expressions;
using FinanceProfile.Api.Application.Concrete;
using FinanceProfile.Api.Application.Constants;
using FinanceProfile.Api.Application.Results;
using FinanceProfile.Api.Domain.Entities;
using FinanceProfile.Api.DTOs;
using FinanceProfile.Api.Infrastructure.Abstract;

namespace FinanceProfile.Tests;

// business rules of FinancialProfileManager; the database and the IQ service are replaced by in-memory fakes
public class FinancialProfileManagerTests
{
    private readonly FakeProfileDal _dal = new();
    private readonly FakeIqClient _iqClient = new();
    private FinancialProfileManager Manager => new(_dal, _iqClient);

    private static UpsertFinancialProfileRequest ValidRequest() => new()
    {
        MonthlyIncome = 30000,
        MonthlyExpenses = 25000,
        MonthlyDebtPayment = 7000,
        TotalDebt = 90000,
        CashReserve = 3000,
        InvestmentAmount = 10000,
        RiskPreference = "HIGH",
        ImpatienceLevel = 5
    };

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task Upsert_WithBlankUserId_IsRejected_AndNothingIsSaved(string userId)
    {
        var result = await Manager.UpsertAsync(userId, ValidRequest());

        Assert.False(result.Success);
        Assert.Equal(Messages.InvalidUserId, result.Message);
        Assert.Empty(_dal.Saved);
    }

    [Fact]
    public async Task Upsert_WithUserIdLongerThanColumn_IsRejected()
    {
        var tooLong = new string('a', FinancialProfile.UserIdMaxLength + 1);

        var result = await Manager.UpsertAsync(tooLong, ValidRequest());

        Assert.False(result.Success);
        Assert.Equal(Messages.InvalidUserId, result.Message);
        Assert.Empty(_dal.Saved);
    }

    [Fact]
    public async Task Upsert_WithUserIdExactlyAtLimit_IsSaved()
    {
        var atLimit = new string('a', FinancialProfile.UserIdMaxLength);

        var result = await Manager.UpsertAsync(atLimit, ValidRequest());

        Assert.True(result.Success);
        Assert.Equal(atLimit, Assert.Single(_dal.Saved).UserId);
    }

    [Fact]
    public async Task Upsert_WithZeroIncome_IsRejected()
    {
        var request = ValidRequest();
        request.MonthlyIncome = 0;

        var result = await Manager.UpsertAsync("u1", request);

        Assert.Equal(Messages.InvalidMonthlyIncome, result.Message);
    }

    [Fact]
    public async Task Upsert_WithNegativeAmount_IsRejected()
    {
        var request = ValidRequest();
        request.CashReserve = -1;

        var result = await Manager.UpsertAsync("u1", request);

        Assert.Equal(Messages.NegativeAmountNotAllowed, result.Message);
    }

    [Theory]
    [InlineData("high")]
    [InlineData("EXTREME")]
    [InlineData("")]
    public async Task Upsert_WithUnknownRiskPreference_IsRejected(string risk)
    {
        var request = ValidRequest();
        request.RiskPreference = risk;

        var result = await Manager.UpsertAsync("u1", request);

        Assert.Equal(Messages.InvalidRiskPreference, result.Message);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(6)]
    public async Task Upsert_WithImpatienceOutOfRange_IsRejected(int level)
    {
        var request = ValidRequest();
        request.ImpatienceLevel = level;

        var result = await Manager.UpsertAsync("u1", request);

        Assert.Equal(Messages.InvalidImpatienceLevel, result.Message);
    }

    [Fact]
    public async Task CalculateIq_WithoutProfile_ReturnsNotFound_AndNeverCallsIq()
    {
        var result = await Manager.CalculateIqAsync("nobody");

        Assert.Equal(Messages.FinancialProfileNotFound, result.Message);
        Assert.Null(_iqClient.LastRequest);
    }

    [Fact]
    public async Task CalculateIq_ForwardsRiskPreferenceAndImpatienceToIq()
    {
        await Manager.UpsertAsync("u1", ValidRequest());

        await Manager.CalculateIqAsync("u1");

        Assert.NotNull(_iqClient.LastRequest);
        Assert.Equal("u1", _iqClient.LastRequest!.UserId);
        Assert.Equal("HIGH", _iqClient.LastRequest.RiskPreference);
        Assert.Equal(5, _iqClient.LastRequest.ImpatienceLevel);
        Assert.Equal(30000, _iqClient.LastRequest.MonthlyIncome);
    }

    private sealed class FakeProfileDal : IFinancialProfileDal
    {
        public List<FinancialProfile> Saved { get; } = new();

        public Task UpsertAsync(FinancialProfile entity)
        {
            Saved.RemoveAll(p => p.UserId == entity.UserId);
            Saved.Add(entity);
            return Task.CompletedTask;
        }

        public Task<FinancialProfile?> GetAsync(Expression<Func<FinancialProfile, bool>> filter)
            => Task.FromResult(Saved.AsQueryable().FirstOrDefault(filter));

        public Task<List<FinancialProfile>> GetAllAsync(Expression<Func<FinancialProfile, bool>>? filter = null)
            => Task.FromResult(filter == null ? Saved.ToList() : Saved.AsQueryable().Where(filter).ToList());

        public Task AddAsync(FinancialProfile entity) => throw new NotSupportedException();
        public Task UpdateAsync(FinancialProfile entity) => throw new NotSupportedException();
        public Task DeleteAsync(FinancialProfile entity) => throw new NotSupportedException();
    }

    private sealed class FakeIqClient : IFinancialIqClient
    {
        public FinancialIqCalculateRequest? LastRequest { get; private set; }

        public Task<IDataResult<FinancialIqCalculateResponse>> CalculateAsync(FinancialIqCalculateRequest request)
        {
            LastRequest = request;
            IDataResult<FinancialIqCalculateResponse> result =
                new SuccessDataResult<FinancialIqCalculateResponse>(new FinancialIqCalculateResponse { Score = 6, Segment = "LOW" }, "ok");
            return Task.FromResult(result);
        }
    }
}
