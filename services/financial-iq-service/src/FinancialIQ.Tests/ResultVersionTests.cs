using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Domain.Entities;

namespace FinancialIQ.Tests;

// rowversion -> resultVersion: the C# side must give the same number as T-SQL's CONVERT(bigint, row_version),
// otherwise calculate (EF read) and /latest (stored procedure) would report different versions for the same row
public class ResultVersionTests
{
    [Fact]
    public void RowVersion_IsReadBigEndian_LikeSqlConvertToBigint()
    {
        // 0x00000000000101F3 is what SQL Server showed for a real row; CONVERT(bigint, ...) gave 66035
        byte[] rowVersion = [0x00, 0x00, 0x00, 0x00, 0x00, 0x01, 0x01, 0xF3];

        Assert.Equal(66035, ResultVersion.FromRowVersion(rowVersion));
    }

    [Fact]
    public void LaterRowVersion_GivesAHigherNumber()
    {
        byte[] earlier = [0, 0, 0, 0, 0, 0, 0x07, 0xD0];
        byte[] later = [0, 0, 0, 0, 0, 0, 0x07, 0xD1];

        Assert.True(ResultVersion.FromRowVersion(later) > ResultVersion.FromRowVersion(earlier));
    }

    [Theory]
    [InlineData(null)]
    [InlineData(new byte[0])]
    [InlineData(new byte[] { 1, 2, 3 })]
    public void MissingOrMalformedRowVersion_IsZero(byte[]? rowVersion)
    {
        Assert.Equal(0, ResultVersion.FromRowVersion(rowVersion));
    }

    [Fact]
    public void CalculateResponse_CarriesTheResultVersion()
    {
        var entity = new FinancialIqResult
        {
            UserId = "u1",
            Score = 62,
            Segment = "MEDIUM",
            FactorBreakdown = "{}",
            RowVersion = [0, 0, 0, 0, 0, 0, 0x03, 0xE8]
        };

        var response = FinancialIqCommandManager.MapToResponse(entity);

        Assert.Equal(1000, response.ResultVersion);
    }
}
