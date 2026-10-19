using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinanceProfile.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddImpatienceLevel : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<int>(
                name: "impatience_level",
                table: "financial_profiles",
                type: "integer",
                nullable: false,
                defaultValue: 3);

            migrationBuilder.AddCheckConstraint(
                name: "financial_profiles_impatience_level_check",
                table: "financial_profiles",
                sql: "impatience_level BETWEEN 1 AND 5");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "financial_profiles_impatience_level_check",
                table: "financial_profiles");

            migrationBuilder.DropColumn(
                name: "impatience_level",
                table: "financial_profiles");
        }
    }
}
