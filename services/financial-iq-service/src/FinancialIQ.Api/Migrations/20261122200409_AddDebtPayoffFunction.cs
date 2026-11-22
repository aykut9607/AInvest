using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace FinancialIQ.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddDebtPayoffFunction : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            // debt amortization schedule as a recursive CTE: each month is computed from the month before it.
            //   anchor member    = month 1, starts from the total debt
            //   recursive member = month n+1, starts from month n's closing balance; stops when the debt is paid
            //                      (closing balance 0) or at @MaxMonths
            // every month: interest = balance x monthly rate (rounded to kuruş), payment = the installment, or less
            // in the last month (only what is left), closing = balance + interest - payment.
            //example lets say debt 10,000, installment 1,000, rate 3.5%: month 1 interest 350, closing 9,350;
            // month 2 interest 327.25, closing 8,677.25 ... month 13 pays the last 526.51 -> 13 months.
            // Inline TVF: cannot carry OPTION (MAXRECURSION), and SQL Server stops a recursive CTE after 100 levels
            // by default, so the caller adds OPTION (MAXRECURSION ...) >= @MaxMonths (EfFinancialIqReadDal does).
            // Anchor and recursive member must return exactly the same types, hence the CASTs to decimal(18,2).
            // Taxes on loan interest (KKDF/BSMV) are not included.
            migrationBuilder.Sql(@"
CREATE OR ALTER FUNCTION dbo.fn_DebtPayoffSchedule
(
    @TotalDebt      decimal(18,2),
    @MonthlyPayment decimal(18,2),
    @MonthlyRate    decimal(9,6),
    @MaxMonths      int
)
RETURNS TABLE
AS
RETURN
WITH schedule AS (
    -- anchor: month 1
    SELECT 1                                   AS month_no,
           CAST(@TotalDebt AS decimal(18,2))   AS opening_balance,
           m.interest,
           m.payment,
           CAST(@TotalDebt + m.interest - m.payment AS decimal(18,2)) AS closing_balance
    FROM (SELECT CAST(ROUND(@TotalDebt * @MonthlyRate, 2) AS decimal(18,2)) AS interest) AS i
    CROSS APPLY (SELECT i.interest,
                        CAST(CASE WHEN @TotalDebt + i.interest <= @MonthlyPayment
                                  THEN @TotalDebt + i.interest
                                  ELSE @MonthlyPayment END AS decimal(18,2)) AS payment) AS m
    WHERE @TotalDebt > 0 AND @MonthlyPayment > 0

    UNION ALL

    -- recursive member: the next month from the previous month's closing balance
    SELECT s.month_no + 1,
           s.closing_balance,
           m.interest,
           m.payment,
           CAST(s.closing_balance + m.interest - m.payment AS decimal(18,2))
    FROM schedule AS s
    CROSS APPLY (SELECT CAST(ROUND(s.closing_balance * @MonthlyRate, 2) AS decimal(18,2)) AS interest) AS i
    CROSS APPLY (SELECT i.interest,
                        CAST(CASE WHEN s.closing_balance + i.interest <= @MonthlyPayment
                                  THEN s.closing_balance + i.interest
                                  ELSE @MonthlyPayment END AS decimal(18,2)) AS payment) AS m
    WHERE s.closing_balance > 0
      AND s.month_no < @MaxMonths
)
SELECT month_no,
       opening_balance,
       interest,
       payment,
       CAST(payment - interest AS decimal(18,2)) AS principal,
       closing_balance
FROM schedule;");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.Sql("DROP FUNCTION IF EXISTS dbo.fn_DebtPayoffSchedule;");
        }
    }
}
