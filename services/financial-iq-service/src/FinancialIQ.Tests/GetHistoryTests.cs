using System.Linq.Expressions;
using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Infrastructure.Abstract;

namespace FinancialIQ.Tests;

// input checks and result handling of GetHistoryAsync; the trend query itself (dbo.fn_IqTrend) runs in SQL Server
public class GetHistoryTests
{
    private readonly FakeTrendDal _dal = new();
    private FinancialIqManager Manager => new(_dal);

    [Theory]
    [InlineData(0)]
    [InlineData(101)]
    public async Task TakeOutsideOneToHundred_IsRejected_AndDatabaseIsNotQueried(int take)
    {
        var result = await Manager.GetHistoryAsync("u1", take);

        Assert.False(result.Success);
        Assert.Equal(Messages.InvalidHistoryTake, result.Message);
        Assert.Null(_dal.LastRequestedUserId);
    }

    [Fact]
    public async Task BlankUserId_IsRejected()
    {
        var result = await Manager.GetHistoryAsync(" ", 12);

        Assert.Equal(Messages.InvalidUserId, result.Message);
    }

    [Fact]
    public async Task UserWithoutHistory_ReturnsNotFoundMessage()
    {
        var result = await Manager.GetHistoryAsync("nobody", 12);

        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqHistoryNotFound, result.Message);
    }

    [Fact]
    public async Task UserWithHistory_ReturnsThePoints_AndPassesTakeThrough()
    {
        _dal.Points.Add(new IqTrendPointResponse { Score = 100, Segment = "HIGH", MovingAverage3 = 100 });
        _dal.Points.Add(new IqTrendPointResponse { Score = 32, Segment = "LOW", ScoreChange = -68, MovingAverage3 = 66 });

        var result = await Manager.GetHistoryAsync("u1", 5);

        Assert.True(result.Success);
        Assert.Equal(2, result.Data!.Count);
        Assert.Equal(-68, result.Data[1].ScoreChange);
        Assert.Equal(("u1", 5), (_dal.LastRequestedUserId, _dal.LastRequestedTake));
    }

    private sealed class FakeTrendDal : IFinancialIqResultDal
    {
        public List<IqTrendPointResponse> Points { get; } = new();
        public string? LastRequestedUserId { get; private set; }
        public int LastRequestedTake { get; private set; }

        public Task<List<IqTrendPointResponse>> GetTrendAsync(string userId, int take)
        {
            LastRequestedUserId = userId;
            LastRequestedTake = take;
            return Task.FromResult(Points.ToList());
        }

        public Task SaveAsync(FinancialIqResult entity) => throw new NotSupportedException();
        public Task<FinancialIqResult?> GetAsync(Expression<Func<FinancialIqResult, bool>> filter) => throw new NotSupportedException();
        public Task<List<FinancialIqResult>> GetAllAsync(Expression<Func<FinancialIqResult, bool>>? filter = null) => throw new NotSupportedException();
        public Task AddAsync(FinancialIqResult entity) => throw new NotSupportedException();
        public Task UpdateAsync(FinancialIqResult entity) => throw new NotSupportedException();
        public Task DeleteAsync(FinancialIqResult entity) => throw new NotSupportedException();
    }
}
