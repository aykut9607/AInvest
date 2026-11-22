using System;
using FinancialIQ.Api.Application.Constants;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddScoringRuleVersions : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // 1) the table of rule sets, with v1 (history) and v2 (active) in it, before anything can point at them
            migrationBuilder.CreateTable(
                name: "scoring_rule_versions",
                columns: table => new
                {
                    version = table.Column<string>(type: "nvarchar(10)", maxLength: 10, nullable: false),
                    description = table.Column<string>(type: "nvarchar(500)", maxLength: 500, nullable: false),
                    rules_json = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    effective_from = table.Column<DateTime>(type: "datetime2(3)", nullable: false),
                    is_active = table.Column<bool>(type: "bit", nullable: false)
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_scoring_rule_versions", x => x.version);
                    table.CheckConstraint("CK_scoring_rule_versions_rules_json", "ISJSON([rules_json]) = 1");
                });

            migrationBuilder.CreateIndex(
                name: "UX_scoring_rule_versions_single_active",
                table: "scoring_rule_versions",
                column: "is_active",
                unique: true,
                filter: "[is_active] = 1");

            // InsertData sends the JSON as a parameter, so quotes inside it need no escaping
            migrationBuilder.InsertData(
                table: "scoring_rule_versions",
                columns: ["version", "description", "rules_json", "effective_from", "is_active"],
                values: new object[,]
                {
                    { "v1", "6 factors 20/20/20/15/15/10 incl. RiskAlignment (self-reported risk vs. capacity from the data); rules VERY_HIGH_INCOME, EXTREME_DEBT",
                      ScoringRuleSnapshots.V1, new DateTime(2026, 11, 13, 0, 0, 0, DateTimeKind.Utc), false },
                    { "v2", "5 factors 25/25/25/15/10, self-reported risk removed; rules VERY_HIGH_INCOME, VERY_HIGH_WEALTH, EXTREME_DEBT",
                      ScoringRuleSnapshots.V2, new DateTime(2026, 11, 22, 0, 0, 0, DateTimeKind.Utc), true }
                });

            // 2) the column on both tables: first NULL-able, filled from the version each breakdown already carries
            //    (v2 breakdowns have "version": "v2", v1 ones have none), then NOT NULL and the foreign key.
            //    Adding it as NOT NULL with a default would have stamped every old row with one guessed version
            foreach (var table in new[] { "financial_iq_results", "iq_history" })
            {
                migrationBuilder.AddColumn<string>(
                    name: "scoring_version",
                    table: table,
                    type: "nvarchar(10)",
                    maxLength: 10,
                    nullable: true);

                // ISJSON first: JSON_VALUE raises an error on text that is not JSON
                migrationBuilder.Sql($@"
UPDATE dbo.{table}
SET scoring_version = COALESCE(
        CASE WHEN ISJSON(factor_breakdown) = 1 THEN JSON_VALUE(factor_breakdown, '$.version') END,
        N'v1');");

                migrationBuilder.AlterColumn<string>(
                    name: "scoring_version",
                    table: table,
                    type: "nvarchar(10)",
                    maxLength: 10,
                    nullable: false,
                    oldClrType: typeof(string),
                    oldType: "nvarchar(10)",
                    oldMaxLength: 10,
                    oldNullable: true);

                migrationBuilder.CreateIndex(
                    name: $"IX_{table}_scoring_version",
                    table: table,
                    column: "scoring_version");

                migrationBuilder.AddForeignKey(
                    name: $"FK_{table}_scoring_rule_versions_scoring_version",
                    table: table,
                    column: "scoring_version",
                    principalTable: "scoring_rule_versions",
                    principalColumn: "version",
                    onDelete: ReferentialAction.Restrict);
            }

            // 3) the save procedure writes the version into both rows (same transaction as before)
            migrationBuilder.Sql(SaveProcedure(withScoringVersion: true));
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql(SaveProcedure(withScoringVersion: false));

            foreach (var table in new[] { "financial_iq_results", "iq_history" })
            {
                migrationBuilder.DropForeignKey(name: $"FK_{table}_scoring_rule_versions_scoring_version", table: table);
                migrationBuilder.DropIndex(name: $"IX_{table}_scoring_version", table: table);
                migrationBuilder.DropColumn(name: "scoring_version", table: table);
            }

            migrationBuilder.DropTable(name: "scoring_rule_versions");
        }

        // usp_SaveIqResult with or without @ScoringVersion (the version from AddSaveIqResultProcedure)
        private static string SaveProcedure(bool withScoringVersion)
        {
            var parameter = withScoringVersion ? ",\n    @ScoringVersion  nvarchar(10)" : "";
            var savedColumn = withScoringVersion ? ", scoring_version nvarchar(10)" : "";
            var update = withScoringVersion ? ",\n                       scoring_version = @ScoringVersion" : "";
            var insertColumn = withScoringVersion ? ", scoring_version" : "";
            var insertValue = withScoringVersion ? ", @ScoringVersion" : "";
            var output = withScoringVersion ? ", inserted.scoring_version" : "";

            return $@"
CREATE OR ALTER PROCEDURE dbo.usp_SaveIqResult
    @UserId          nvarchar(100),
    @Score           int,
    @Segment         nvarchar(10),
    @FactorBreakdown nvarchar(max){parameter}
AS
BEGIN
    SET NOCOUNT ON;
    -- any run-time error rolls back the whole transaction (no half-written result without its history row)
    SET XACT_ABORT ON;

    -- the row MERGE actually wrote, captured with OUTPUT so the history row copies exactly that
    DECLARE @saved TABLE (user_id nvarchar(100), score int, segment nvarchar(10), factor_breakdown nvarchar(max){savedColumn});

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
                       updated_at = SYSUTCDATETIME(){update}
        WHEN NOT MATCHED THEN
            INSERT (id, user_id, score, segment, factor_breakdown, created_at, updated_at{insertColumn})
            VALUES (NEWID(), @UserId, @Score, @Segment, @FactorBreakdown, SYSUTCDATETIME(), SYSUTCDATETIME(){insertValue})
        OUTPUT inserted.user_id, inserted.score, inserted.segment, inserted.factor_breakdown{output}
            INTO @saved (user_id, score, segment, factor_breakdown{insertColumn});

        -- append-only history in the same transaction: either both rows are written or neither
        INSERT INTO dbo.iq_history (user_id, score, segment, factor_breakdown{insertColumn})
        SELECT user_id, score, segment, factor_breakdown{insertColumn}
        FROM @saved;

        COMMIT TRANSACTION;
    END TRY
    BEGIN CATCH
        IF XACT_STATE() <> 0
            ROLLBACK TRANSACTION;
        -- re-raise the original error (number and message) to the caller
        THROW;
    END CATCH
END;";
        }
    }
}
