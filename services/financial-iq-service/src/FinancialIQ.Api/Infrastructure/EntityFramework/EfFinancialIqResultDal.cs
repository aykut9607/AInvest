using System.Data;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Infrastructure.Abstract;
using Microsoft.Data.SqlClient;
using Microsoft.EntityFrameworkCore;

namespace FinancialIQ.Api.Infrastructure.EntityFramework;

public class EfFinancialIqResultDal : EfEntityRepositoryBase<FinancialIqResult, FinancialIqDbContext>, IFinancialIqResultDal
{
    public EfFinancialIqResultDal(FinancialIqDbContext context) : base(context)
    {
    }

    // one call to usp_SaveIqResult: the database decides insert or update (MERGE) and writes the history row
    // in the same transaction. Values travel as typed parameters, never as SQL text, so no SQL injection.
    public async Task SaveAsync(FinancialIqResult entity)
    {
        var parameters = new[]
        {
            new SqlParameter("@UserId", SqlDbType.NVarChar, FinancialIqResult.UserIdMaxLength) { Value = entity.UserId },
            new SqlParameter("@Score", SqlDbType.Int) { Value = entity.Score },
            new SqlParameter("@Segment", SqlDbType.NVarChar, FinancialIqResult.SegmentMaxLength) { Value = entity.Segment },
            // size -1 = nvarchar(max)
            new SqlParameter("@FactorBreakdown", SqlDbType.NVarChar, -1) { Value = entity.FactorBreakdown }
        };

        await _context.Database.ExecuteSqlRawAsync(
            "EXEC dbo.usp_SaveIqResult @UserId, @Score, @Segment, @FactorBreakdown",
            parameters);
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
