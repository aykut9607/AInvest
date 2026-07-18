using FinanceProfile.Api.Core.DataAccess.EntityFramework;
using FinanceProfile.Api.Domain.Entities;
using FinanceProfile.Api.Infrastructure.Abstract;
using Microsoft.EntityFrameworkCore;

namespace FinanceProfile.Api.Infrastructure.EntityFramework;

public class EfFinancialProfileDal : EfEntityRepositoryBase<FinancialProfile, FinanceDbContext>, IFinancialProfileDal
{
    public EfFinancialProfileDal(FinanceDbContext context) : base(context)
    {
    }

    public async Task UpsertAsync(FinancialProfile entity)
    {
        var existingEntity= await _context.FinancialProfiles.FirstOrDefaultAsync
        (p=> p.UserId==entity.UserId);
        if (existingEntity == null)
        {
            entity.Id=Guid.NewGuid();
            await AddAsync(entity);
        }
        else
        {
            entity.Id = existingEntity.Id;
            _context.Entry(existingEntity).CurrentValues.SetValues(entity);
        }
        await _context.SaveChangesAsync();
    }
}