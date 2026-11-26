using FinancialIQ.Api.Application.Constants;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddScoringRulesV3 : Migration
    {
        // the v3 row of scoring_rule_versions; rules_json is the frozen snapshot, never the live document
        private const string Description =
            "5 linear factors 30/25/10/30/5 (variant v3c-i5), no TL rules: solvency cap (net debt 5 to 15 years of income) " +
            "and wealth runway (25 years of expenses); appliedRule SOLVENCY_CAP / WEALTH_RUNWAY is a label only";

        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // 1) switch the active version (v2) off FIRST: the filtered unique index UX_scoring_rule_versions_single_active
            //    allows only one row with is_active = 1, so activating v3 while v2 is still active would fail
            // 2) insert v3 as the active version. The row is already there when an earlier Down kept it because results
            //    pointed at it (see Down); then it is only activated again, its rules_json stays as it was (frozen).
            //    The JSON goes in as a literal (with ' doubled) because the insert is conditional; ISJSON checks it.
            //    v1 and v2 are not touched. usp_SaveIqResult needs no change: it writes @ScoringVersion, and the foreign
            //    key now finds 'v3'; no SQL object reads the factors inside factor_breakdown
            migrationBuilder.Sql($@"
UPDATE dbo.scoring_rule_versions SET is_active = 0 WHERE is_active = 1;

IF NOT EXISTS (SELECT 1 FROM dbo.scoring_rule_versions WHERE version = N'v3')
    INSERT INTO dbo.scoring_rule_versions (version, description, rules_json, effective_from, is_active)
    VALUES (N'v3', N'{Literal(Description)}', N'{Literal(ScoringRuleSnapshots.V3)}', '2026-11-24T00:00:00', 1);
ELSE
    UPDATE dbo.scoring_rule_versions SET is_active = 1 WHERE version = N'v3';");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // v2 becomes the active version again (v3 off first, same index as above).
            // The v3 row is deleted only while no result or history row points at it: the foreign keys are RESTRICT,
            // and deleting the rules of stored scores would leave them unexplainable. If v3 results exist, the row
            // stays (inactive) and a later Up activates it again instead of inserting it
            migrationBuilder.Sql(@"
UPDATE dbo.scoring_rule_versions SET is_active = 0 WHERE version = N'v3';
UPDATE dbo.scoring_rule_versions SET is_active = 1 WHERE version = N'v2';

IF NOT EXISTS (SELECT 1 FROM dbo.financial_iq_results WHERE scoring_version = N'v3')
   AND NOT EXISTS (SELECT 1 FROM dbo.iq_history WHERE scoring_version = N'v3')
    DELETE FROM dbo.scoring_rule_versions WHERE version = N'v3';");
        }

        // text inside an N'...' literal: a single quote is written twice
        private static string Literal(string text) => text.Replace("'", "''");
    }
}
