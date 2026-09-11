using System.Linq.Expressions;
using Microsoft.EntityFrameworkCore;
using FinancialIQ.Api.Domain.Common;
using FinancialIQ.Api.Infrastructure.Abstract;

namespace FinancialIQ.Api.Infrastructure.EntityFramework;
public class EfEntityRepositoryBase<TEntity,TContext>: IEntityRepository<TEntity> 
where TEntity: class,IEntity,new()
where TContext : DbContext
{
    protected readonly TContext _context;

    public EfEntityRepositoryBase(TContext context)
    {
        _context = context;
    }

    public async Task AddAsync(TEntity entity)
    {
        var addedEntity  = _context.Entry(entity);
        addedEntity.State = EntityState.Added;
        await _context.SaveChangesAsync();
    }

    public async Task DeleteAsync(TEntity entity)
    {
        var deletedEntity =_context.Entry(entity);
        deletedEntity.State=EntityState.Deleted;
        await _context.SaveChangesAsync();
    } 

    public async Task UpdateAsync(TEntity entity)
    {
        var updatedEntity=_context.Entry(entity);
        updatedEntity.State=EntityState.Modified;
        await _context.SaveChangesAsync();
    }

    public async Task<TEntity?> GetAsync(Expression<Func<TEntity, bool>> filter)
    {
        return await _context.Set<TEntity>().FirstOrDefaultAsync(filter);
    }

    public async Task<List<TEntity>> GetAllAsync(Expression<Func<TEntity, bool>>? filter = null)
    {
        return filter == null
            ? await _context.Set<TEntity>().ToListAsync()
            : await _context.Set<TEntity>().Where(filter).ToListAsync();
    }
}