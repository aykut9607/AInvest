using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Tests;

// reading the rule table (scoring_rule_versions is faked; the real rows come from the AddScoringRuleVersions migration)
public class ScoringRulesQueryTests
{
    private readonly FakeReadDal _readDal = new();
    private FinancialIqQueryManager Manager => new(_readDal);

    public ScoringRulesQueryTests()
    {
        _readDal.ScoringVersions.Add(new ScoringRulesResponse { Version = "v2", IsActive = true });
        _readDal.ScoringVersions.Add(new ScoringRulesResponse { Version = "v1", IsActive = false });
    }

    [Fact]
    public async Task Current_IsTheActiveVersion()
    {
        var result = await Manager.GetScoringRulesAsync("current");

        Assert.True(result.Success);
        Assert.Equal("v2", result.Data!.Version);
    }

    [Theory]
    [InlineData("v1")]
    [InlineData("V1")]
    public async Task AnOlderVersion_CanStillBeRead(string version)
    {
        var result = await Manager.GetScoringRulesAsync(version);

        Assert.Equal("v1", result.Data!.Version);
    }

    [Fact]
    public async Task UnknownVersion_IsNotFound()
    {
        var result = await Manager.GetScoringRulesAsync("v9");

        Assert.False(result.Success);
        Assert.Equal(Messages.ScoringVersionNotFound, result.Message);
    }

    [Fact]
    public async Task AllVersions_AreListed()
    {
        var result = await Manager.GetScoringRulesAsync();

        Assert.Equal(["v2", "v1"], result.Data!.Select(v => v.Version));
    }
}
