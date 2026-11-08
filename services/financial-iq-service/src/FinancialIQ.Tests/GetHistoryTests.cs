using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Tests;

// input checks and result handling of GetHistoryAsync (query side); the trend query itself (dbo.fn_IqTrend) runs in SQL Server
public class GetHistoryTests
{
    private readonly FakeReadDal _dal = new();
    private FinancialIqQueryManager Manager => new(_dal);

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
}
