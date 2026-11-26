using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinanceProfile.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddPaymentDiscipline : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "bills_on_time",
                table: "financial_profiles",
                type: "character varying(20)",
                maxLength: 20,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "late_payments",
                table: "financial_profiles",
                type: "character varying(20)",
                maxLength: 20,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "minimum_payment_months",
                table: "financial_profiles",
                type: "character varying(20)",
                maxLength: 20,
                nullable: true);

            migrationBuilder.AddCheckConstraint(
                name: "financial_profiles_bills_on_time_check",
                table: "financial_profiles",
                sql: "bills_on_time IN ('ALL', 'ALMOST_ALL', 'MOST', 'SOME', 'VERY_FEW')");

            migrationBuilder.AddCheckConstraint(
                name: "financial_profiles_late_payments_check",
                table: "financial_profiles",
                sql: "late_payments IN ('NONE', 'ONCE', 'TWICE_OR_MORE')");

            migrationBuilder.AddCheckConstraint(
                name: "financial_profiles_minimum_payment_months_check",
                table: "financial_profiles",
                sql: "minimum_payment_months IN ('NONE', 'ONE_TWO', 'THREE_FIVE', 'SIX_PLUS', 'NO_CARD')");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropCheckConstraint(
                name: "financial_profiles_bills_on_time_check",
                table: "financial_profiles");

            migrationBuilder.DropCheckConstraint(
                name: "financial_profiles_late_payments_check",
                table: "financial_profiles");

            migrationBuilder.DropCheckConstraint(
                name: "financial_profiles_minimum_payment_months_check",
                table: "financial_profiles");

            migrationBuilder.DropColumn(
                name: "bills_on_time",
                table: "financial_profiles");

            migrationBuilder.DropColumn(
                name: "late_payments",
                table: "financial_profiles");

            migrationBuilder.DropColumn(
                name: "minimum_payment_months",
                table: "financial_profiles");
        }
    }
}
