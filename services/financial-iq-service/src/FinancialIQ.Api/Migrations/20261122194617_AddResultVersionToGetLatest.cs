using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddResultVersionToGetLatest : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // the read procedure also returns the row's version. rowversion is 8 bytes; CONVERT(bigint, ...) reads
            // them big-endian, the same number ResultVersion.FromRowVersion computes on the C# side
            migrationBuilder.Sql(@"
CREATE OR ALTER PROCEDURE dbo.usp_GetLatestIqResult
    @UserId nvarchar(100)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT id                          AS Id,
           user_id                     AS UserId,
           score                       AS Score,
           segment                     AS Segment,
           factor_breakdown            AS FactorBreakdown,
           created_at                  AS CreatedAt,
           updated_at                  AS UpdatedAt,
           CONVERT(bigint, row_version) AS ResultVersion
    FROM dbo.financial_iq_results
    WHERE user_id = @UserId;
END");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // back to the version from AddGetLatestIqResultProcedure (without ResultVersion)
            migrationBuilder.Sql(@"
CREATE OR ALTER PROCEDURE dbo.usp_GetLatestIqResult
    @UserId nvarchar(100)
AS
BEGIN
    SET NOCOUNT ON;

    SELECT id               AS Id,
           user_id          AS UserId,
           score            AS Score,
           segment          AS Segment,
           factor_breakdown AS FactorBreakdown,
           created_at       AS CreatedAt,
           updated_at       AS UpdatedAt
    FROM dbo.financial_iq_results
    WHERE user_id = @UserId;
END");
        }
    }
}
