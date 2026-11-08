using System.Data;
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
}
