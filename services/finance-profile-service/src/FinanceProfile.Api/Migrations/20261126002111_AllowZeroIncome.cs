using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinanceProfile.Api.Migrations
{
    /// <inheritdoc />
    public partial class AllowZeroIncome : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "financial_profiles_monthly_income_check",
                table: "financial_profiles");

            migrationBuilder.AddCheckConstraint(
                name: "financial_profiles_monthly_income_check",
                table: "financial_profiles",
                sql: "monthly_income >= 0");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "financial_profiles_monthly_income_check",
                table: "financial_profiles");

            migrationBuilder.AddCheckConstraint(
                name: "financial_profiles_monthly_income_check",
                table: "financial_profiles",
                sql: "monthly_income > 0");
        }
    }
}
