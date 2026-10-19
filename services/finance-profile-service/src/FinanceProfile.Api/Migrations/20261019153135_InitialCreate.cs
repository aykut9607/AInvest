using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinanceProfile.Api.Migrations
{
    /// <inheritdoc />
    public partial class InitialCreate : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "financial_profiles",
                columns: table => new
                {
                    id = table.Column<Guid>(type: "uuid", nullable: false, defaultValueSql: "gen_random_uuid()"),
                    user_id = table.Column<string>(type: "character varying(100)", maxLength: 100, nullable: false),
                    monthly_income = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    monthly_expenses = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    monthly_debt_payment = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    total_debt = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    cash_reserve = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    investment_amount = table.Column<decimal>(type: "numeric(18,2)", precision: 18, scale: 2, nullable: false),
                    risk_preference = table.Column<string>(type: "character varying(20)", maxLength: 20, nullable: false),
                    created_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()"),
                    updated_at = table.Column<DateTime>(type: "timestamp with time zone", nullable: false, defaultValueSql: "now()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("financial_profiles_pkey", x => x.id);
                    table.CheckConstraint("financial_profiles_cash_reserve_check", "cash_reserve >= 0");
                    table.CheckConstraint("financial_profiles_investment_amount_check", "investment_amount >= 0");
                    table.CheckConstraint("financial_profiles_monthly_debt_payment_check", "monthly_debt_payment >= 0");
                    table.CheckConstraint("financial_profiles_monthly_expenses_check", "monthly_expenses >= 0");
                    table.CheckConstraint("financial_profiles_monthly_income_check", "monthly_income > 0");
                    table.CheckConstraint("financial_profiles_risk_preference_check", "risk_preference IN ('LOW', 'MEDIUM', 'HIGH')");
                    table.CheckConstraint("financial_profiles_total_debt_check", "total_debt >= 0");
                });

            migrationBuilder.CreateIndex(
                name: "financial_profiles_user_id_key",
                table: "financial_profiles",
                column: "user_id",
                unique: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "financial_profiles");
        }
    }
}
