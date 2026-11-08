using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddIqHistory : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.CreateTable(
                name: "iq_history",
                columns: table => new
                {
                    id = table.Column<long>(type: "bigint", nullable: false)
                        .Annotation("SqlServer:Identity", "1, 1"),
                    user_id = table.Column<string>(type: "nvarchar(100)", maxLength: 100, nullable: false),
                    score = table.Column<int>(type: "int", nullable: false),
                    segment = table.Column<string>(type: "nvarchar(10)", maxLength: 10, nullable: false),
                    factor_breakdown = table.Column<string>(type: "nvarchar(max)", nullable: false),
                    calculated_at = table.Column<DateTime>(type: "datetime2(3)", nullable: false, defaultValueSql: "SYSUTCDATETIME()")
                },
                constraints: table =>
                {
                    table.PrimaryKey("PK_iq_history", x => x.id);
                    table.CheckConstraint("CK_iq_history_score", "[score] BETWEEN 0 AND 100");
                });

            migrationBuilder.CreateIndex(
                name: "IX_iq_history_user_id_calculated_at",
                table: "iq_history",
                columns: new[] { "user_id", "calculated_at" },
                descending: new[] { false, true })
                .Annotation("SqlServer:Include", new[] { "score", "segment" });
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropTable(
                name: "iq_history");
        }
    }
}
