using FinancialIQ.Api.Application.Constants;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddScoringRulesV21 : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // one active version at a time (filtered unique index): switch v2 off first, then insert v2.1 as the active one
            migrationBuilder.Sql("UPDATE scoring_rule_versions SET is_active = 0 WHERE version = 'v2';");
            migrationBuilder.InsertData(
                table: "scoring_rule_versions",
                columns: ["version", "description", "rules_json", "effective_from", "is_active"],
                values: new object[] { "v2.1", "v2 factors; the cliffs around the special rules removed (wealth floor at 25 years of outgoings, income floor, debt cap above 3 years of income); income 0 accepted",
                                       ScoringRuleSnapshots.V2_1, new DateTime(2026, 11, 26, 0, 0, 0, DateTimeKind.Utc), true });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            // results already stored with v2.1 point at it (foreign key): they must be recalculated or removed before going back
            migrationBuilder.DeleteData(table: "scoring_rule_versions", keyColumn: "version", keyValue: "v2.1");
            migrationBuilder.Sql("UPDATE scoring_rule_versions SET is_active = 1 WHERE version = 'v2';");
        }
    }
}
