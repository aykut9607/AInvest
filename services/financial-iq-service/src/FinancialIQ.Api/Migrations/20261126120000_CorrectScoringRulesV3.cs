using FinancialIQ.Api.Application.Constants;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class CorrectScoringRulesV3 : Migration
    {
        // the 26 Nov correction of v3, kept under the same version name (v3 had been live for one day, no real users):
        // the reserve months, the 6-month target and the runway are measured in max(expenses, 2000 TL) instead of
        // max(expenses, 10% of the income), which made a higher income lower the score. No table or index changes;
        // only the rules_json of the v3 row. Results already stored as v3 keep their score until they are recalculated

        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // the JSON goes in as a literal (with ' doubled); the ISJSON check constraint validates it
            migrationBuilder.Sql($@"
UPDATE dbo.scoring_rule_versions SET rules_json = N'{Literal(ScoringRuleSnapshots.V3)}' WHERE version = N'v3';");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // back to the first v3 text, exactly what AddScoringRulesV3 inserted
            migrationBuilder.Sql($@"
UPDATE dbo.scoring_rule_versions SET rules_json = N'{Literal(ScoringRuleSnapshots.V3Initial)}' WHERE version = N'v3';");
        }

        // text inside an N'...' literal: a single quote is written twice
        private static string Literal(string text) => text.Replace("'", "''");
    }
}
