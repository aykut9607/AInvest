using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddLowSegmentFilteredIndex : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateIndex(
                name: "IX_financial_iq_results_low_segment",
                table: "financial_iq_results",
                column: "updated_at",
                descending: new bool[0],
                filter: "[segment] = N'LOW'")
                .Annotation("SqlServer:Include", new[] { "user_id", "score" });

            // the query the filtered index is for. The filter is the literal N'LOW' on purpose: with
            // "WHERE segment = @Segment" SQL Server must build a plan that also works for 'HIGH', so it may not use
            // an index that only holds LOW rows and scans the table instead (shown in perf/filtered-index.md).
            // TOP (@Take) + ORDER BY updated_at DESC = read the first @Take entries of the index and stop.
            // For Notification / Ops (Faz 5); not exposed through the gateway
            migrationBuilder.Sql(@"
CREATE OR ALTER PROCEDURE dbo.usp_GetLowSegmentResults
    @Take int = 50
AS
BEGIN
    SET NOCOUNT ON;

    SELECT TOP (@Take)
           user_id    AS UserId,
           score      AS Score,
           updated_at AS UpdatedAt
    FROM dbo.financial_iq_results
    WHERE segment = N'LOW'
    ORDER BY updated_at DESC;
END");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql("DROP PROCEDURE IF EXISTS dbo.usp_GetLowSegmentResults;");

            migrationBuilder.DropIndex(
                name: "IX_financial_iq_results_low_segment",
                table: "financial_iq_results");
        }
    }
}
