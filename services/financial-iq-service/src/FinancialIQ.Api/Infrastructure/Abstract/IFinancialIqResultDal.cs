using FinancialIQ.Api.Domain.Entities;

namespace FinancialIQ.Api.Infrastructure.Abstract;

public interface IFinancialIqResultDal:IEntityRepository<FinancialIqResult>
{     
       Task UpsertAsync(FinancialIqResult entity);
}