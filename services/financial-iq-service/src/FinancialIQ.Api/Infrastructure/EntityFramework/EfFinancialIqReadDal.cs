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
}
