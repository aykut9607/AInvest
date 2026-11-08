using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Tests;

// GetLatestAsync (query side): checks the id before asking the database and maps "no row" to a not-found message
public class GetLatestTests
{
    private readonly FakeReadDal _dal = new();
    private FinancialIqQueryManager Manager => new(_dal);

    [Theory]
    [InlineData("")]
    [InlineData("   ")]
    public async Task BlankUserId_IsRejected_AndDatabaseIsNotQueried(string userId)
    {
        var result = await Manager.GetLatestAsync(userId);

        Assert.False(result.Success);
        Assert.Equal(Messages.InvalidUserId, result.Message);
        Assert.Null(_dal.LastRequestedUserId);
    }

    [Fact]
    public async Task UserIdLongerThan100_IsRejected()
    {
        var result = await Manager.GetLatestAsync(new string('a', 101));

        Assert.Equal(Messages.InvalidUserId, result.Message);
        Assert.Null(_dal.LastRequestedUserId);
    }

    [Fact]
    public async Task UnknownUser_ReturnsNotFoundMessage()
    {
        var result = await Manager.GetLatestAsync("nobody");

        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqResultNotFound, result.Message);
    }

    [Fact]
    public async Task KnownUser_ReturnsTheStoredResultAsIs()
    {
        _dal.Latest["u1"] = new FinancialIqResultResponse { UserId = "u1", Score = 88, Segment = "HIGH" };

        var result = await Manager.GetLatestAsync("u1");

        Assert.True(result.Success);
        Assert.Equal((88, "HIGH"), (result.Data!.Score, result.Data.Segment));
    }
}
