using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddIqTrendFunction : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // inline table-valued function: a single SELECT with a parameter, so it works like a parameterised view.
            // Unlike a stored procedure it can be used inside another query (FROM dbo.fn_IqTrend(...) WHERE ... ORDER BY ...)
            // and the optimizer folds it into that query, so the covering index on iq_history is still used.
            migrationBuilder.Sql(@"
CREATE OR ALTER FUNCTION dbo.fn_IqTrend (@UserId nvarchar(100))
RETURNS TABLE
AS
RETURN
    -- the CTE computes the window values once, the outer SELECT can then use them by name (score - previous_score)
    WITH ordered AS (
        SELECT
            calculated_at,
            score,
            segment,
            -- score of the calculation just before this one (NULL for the first one)
            LAG(score) OVER (ORDER BY calculated_at, id) AS previous_score,
            -- average of this and the 2 previous scores; the ROWS frame is written out on purpose, because without it
            -- SQL Server uses RANGE UNBOUNDED PRECEDING, which averages everything so far and is slower
            AVG(CAST(score AS decimal(5, 2))) OVER (ORDER BY calculated_at, id
                                                   ROWS BETWEEN 2 PRECEDING AND CURRENT ROW) AS moving_avg_3,
            -- 1 = newest calculation, so the caller can ask for 'the last N' with recency_rank <= N
            ROW_NUMBER() OVER (ORDER BY calculated_at DESC, id DESC) AS recency_rank
        FROM dbo.iq_history
        WHERE user_id = @UserId
    )
    SELECT
        calculated_at,
        score,
        segment,
        score - previous_score AS score_change,
        moving_avg_3,
        recency_rank
    FROM ordered;");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql("DROP FUNCTION IF EXISTS dbo.fn_IqTrend;");
        }
    }
}
