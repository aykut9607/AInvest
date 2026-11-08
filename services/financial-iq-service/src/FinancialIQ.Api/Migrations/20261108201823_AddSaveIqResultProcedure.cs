using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddSaveIqResultProcedure : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // replaces the C# "read, then insert or update" upsert: two requests for the same new user could both
            // read "no row" and both insert. Here the check and the write are one statement inside the database.
            migrationBuilder.Sql(@"
CREATE OR ALTER PROCEDURE dbo.usp_SaveIqResult
    @UserId          nvarchar(100),
    @Score           int,
    @Segment         nvarchar(10),
    @FactorBreakdown nvarchar(max)
AS
BEGIN
    SET NOCOUNT ON;
    -- any run-time error rolls back the whole transaction (no half-written result without its history row)
    SET XACT_ABORT ON;

    -- the row MERGE actually wrote, captured with OUTPUT so the history row copies exactly that
    DECLARE @saved TABLE (user_id nvarchar(100), score int, segment nvarchar(10), factor_breakdown nvarchar(max));

    BEGIN TRY
        BEGIN TRANSACTION;

        -- HOLDLOCK = SERIALIZABLE for this statement: it locks the key (or the empty key range for a new user)
        -- until the transaction ends, so a second session waits instead of also taking the INSERT branch
        MERGE dbo.financial_iq_results WITH (HOLDLOCK) AS target
        USING (SELECT @UserId AS user_id) AS source
           ON target.user_id = source.user_id
        WHEN MATCHED THEN
            UPDATE SET score = @Score,
                       segment = @Segment,
                       factor_breakdown = @FactorBreakdown,
                       updated_at = SYSUTCDATETIME()
        WHEN NOT MATCHED THEN
            INSERT (id, user_id, score, segment, factor_breakdown, created_at, updated_at)
            VALUES (NEWID(), @UserId, @Score, @Segment, @FactorBreakdown, SYSUTCDATETIME(), SYSUTCDATETIME())
        OUTPUT inserted.user_id, inserted.score, inserted.segment, inserted.factor_breakdown
            INTO @saved (user_id, score, segment, factor_breakdown);

        -- append-only history in the same transaction: either both rows are written or neither
        INSERT INTO dbo.iq_history (user_id, score, segment, factor_breakdown)
        SELECT user_id, score, segment, factor_breakdown
        FROM @saved;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0
            ROLLBACK TRANSACTION;
        -- re-raise the original error (number and message) to the caller
        THROW;
    END CATCH
END;");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql("DROP PROCEDURE IF EXISTS dbo.usp_SaveIqResult;");
        }
    }
}
