using FinancialIQ.Api.Core.DataAccess.EntityFramework;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Infrastructure.Abstract;
using Microsoft.EntityFrameworkCore;

namespace FinancialIQ.Api.Infrastructure.EntityFramework;

public class EfFinancialIqResultDal : EfEntityRepositoryBase<FinancialIqResult, FinancialIqDbContext>, IFinancialIqResultDal
{
    public EfFinancialIqResultDal(FinancialIqDbContext context) : base(context)
    {
    }

    public async Task UpsertAsync(FinancialIqResult entity)
    {
        var existingResult = await _context.FinancialIqResults
            .FirstOrDefaultAsync(x => x.UserId == entity.UserId);

        if (existingResult == null)
        {
            entity.Id = Guid.NewGuid();
            await _context.FinancialIqResults.AddAsync(entity);
        }
        else
        {
            _context.Entry(existingResult).CurrentValues.SetValues(entity);
        }

        await _context.SaveChangesAsync();
    }
}