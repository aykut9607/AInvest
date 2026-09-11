using FinanceProfile.Api.Domain.Entities;

namespace FinanceProfile.Api.Infrastructure.Abstract;

public interface IFinancialProfileDal:IEntityRepository<FinancialProfile>
{
    public  Task UpsertAsync(FinancialProfile entity);
}