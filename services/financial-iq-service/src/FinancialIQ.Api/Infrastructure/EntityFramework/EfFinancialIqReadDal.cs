using System.Data;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Infrastructure.Abstract;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;

namespace FinancialIQ.Api.Infrastructure.EntityFramework;

public class EfFinancialIqReadDal : IFinancialIqReadDal
{
    private readonly FinancialIqDbContext _context;

    public EfFinancialIqReadDal(FinancialIqDbContext context)
    {
        _context = context;
    }

    public async Task<FinancialIqResultResponse?> GetLatestAsync(string userId)
    {
        var userIdParameter = new SqlParameter("@UserId", SqlDbType.NVarChar, FinancialIqResult.UserIdMaxLength)
        {
            Value = userId
        };

        // EXEC cannot be wrapped in another SELECT, so no LINQ on top (FirstOrDefault would try that):
        // read the (at most one) row as a list, then pick it in memory
        var rows = await _context.Database
            .SqlQueryRaw<LatestIqResultRow>("EXEC dbo.usp_GetLatestIqResult @UserId", userIdParameter)
            .ToListAsync();

        var row = rows.FirstOrDefault();
        if (row == null) return null;

        // the column holds JSON text; the response carries it as a JSON object (contract v2)
        return new FinancialIqResultResponse
        {
            Id = row.Id,
            UserId = row.UserId,
            Score = row.Score,
            Segment = row.Segment,
            FactorBreakdown = FactorBreakdownJson.ToElement(row.FactorBreakdown),
            CreatedAt = row.CreatedAt,
            UpdatedAt = row.UpdatedAt,
            ResultVersion = row.ResultVersion
        };
    }

    // the shape usp_GetLatestIqResult returns (same aliases), with the breakdown still as text
    private sealed class LatestIqResultRow
    {
        public Guid Id { get; set; }
        public string UserId { get; set; } = string.Empty;
        public int Score { get; set; }
        public string Segment { get; set; } = string.Empty;
        public string FactorBreakdown { get; set; } = string.Empty;
        public DateTime CreatedAt { get; set; }
        public DateTime UpdatedAt { get; set; }
        // CONVERT(bigint, row_version) in the procedure
        public long ResultVersion { get; set; }
    }

    public async Task<List<IqTrendPointResponse>> GetTrendAsync(string userId, int take)
    {
        // the interpolated values become SQL parameters (@p0, @p1), not text. The aliases match the DTO's property
        // names so EF can fill it; the extra ORDER BY is composed on top because the function itself returns a set
        return await _context.Database
            .SqlQuery<IqTrendPointResponse>($@"
                SELECT calculated_at AS CalculatedAt,
                       score         AS Score,
                       segment       AS Segment,
                       score_change  AS ScoreChange,
                       moving_avg_3  AS MovingAverage3
                FROM dbo.fn_IqTrend({userId})
                WHERE recency_rank <= {take}")
            .OrderBy(p => p.CalculatedAt)
            .ToListAsync();
    }

    // OPTION (MAXRECURSION) must be the last clause of the statement and only takes a literal, not a parameter,
    // so the SQL is a constant (no LINQ on top: EF would wrap it in another SELECT). Without the option SQL Server
    // stops a recursive CTE after 100 levels (error 530), i.e. any debt longer than 100 months would fail
    private const int MaxRecursion = 600;
    private const string DebtPayoffScheduleSql = @"
        SELECT month_no        AS Month,
               opening_balance AS OpeningBalance,
               interest        AS Interest,
               payment         AS Payment,
               principal       AS Principal,
               closing_balance AS ClosingBalance
        FROM dbo.fn_DebtPayoffSchedule(@TotalDebt, @MonthlyPayment, @MonthlyRate, @MaxMonths)
        ORDER BY month_no
        OPTION (MAXRECURSION 600)";

    public async Task<List<DebtPayoffMonth>> GetDebtPayoffScheduleAsync(decimal totalDebt, decimal monthlyPayment, decimal monthlyRate, int maxMonths)
    {
        // the function stops at @MaxMonths, the recursion limit must allow that many months
        ArgumentOutOfRangeException.ThrowIfGreaterThan(maxMonths, MaxRecursion);

        var parameters = new[]
        {
            new SqlParameter("@TotalDebt", SqlDbType.Decimal) { Precision = 18, Scale = 2, Value = totalDebt },
            new SqlParameter("@MonthlyPayment", SqlDbType.Decimal) { Precision = 18, Scale = 2, Value = monthlyPayment },
            new SqlParameter("@MonthlyRate", SqlDbType.Decimal) { Precision = 9, Scale = 6, Value = monthlyRate },
            new SqlParameter("@MaxMonths", SqlDbType.Int) { Value = maxMonths }
        };

        return await _context.Database
            .SqlQueryRaw<DebtPayoffMonth>(DebtPayoffScheduleSql, parameters)
            .ToListAsync();
    }
}
