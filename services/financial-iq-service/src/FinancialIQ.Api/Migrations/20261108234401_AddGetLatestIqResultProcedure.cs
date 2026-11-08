using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddGetLatestIqResultProcedure : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // read side of CQRS-lite: the "latest result" query lives in the database next to usp_SaveIqResult.
            // WHERE user_id = @UserId is answered by UX_financial_iq_results_user_id (Index Seek, at most 1 row).
            // The column aliases are the DTO's property names, so EF fills FinancialIqResultResponse directly.
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

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql("DROP PROCEDURE IF EXISTS dbo.usp_GetLatestIqResult;");
        }
    }
}
