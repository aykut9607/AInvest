using System.Linq.Expressions;
using FinancialIQ.Api.Domain.Common;

namespace FinancialIQ.Api.Infrastructure.Abstract;

public interface IEntityRepository<T>where T : class, IEntity, new()
{
        Task<List<T>> GetAllAsync(Expression<Func<T, bool>>? filter = null);
        Task<T?> GetAsync(Expression<Func<T, bool>> filter);
        Task AddAsync(T entity);
        Task UpdateAsync(T entity);
        Task DeleteAsync(T entity);
}