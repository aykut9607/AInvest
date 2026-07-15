using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Core.DataAccess;

namespace FinancialIQ.Api.Infrastructure.Abstract;

public interface IFinancialIqResultDal:IEntityRepository<FinancialIqResult>
{     
       Task UpsertAsync(FinancialIqResult entity);
}