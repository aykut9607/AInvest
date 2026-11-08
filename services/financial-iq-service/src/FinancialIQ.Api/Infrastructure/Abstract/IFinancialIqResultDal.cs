using FinancialIQ.Api.Domain.Entities;

namespace FinancialIQ.Api.Infrastructure.Abstract;

// write side data access: the generic repository for the entity + the save procedure
public interface IFinancialIqResultDal:IEntityRepository<FinancialIqResult>
{
       // insert-or-update the latest result and append a history row (dbo.usp_SaveIqResult)
       Task SaveAsync(FinancialIqResult entity);
}
