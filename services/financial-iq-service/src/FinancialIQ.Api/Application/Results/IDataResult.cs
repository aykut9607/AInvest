namespace FinancialIQ.Api.Application.Results
{
    public interface IDataResult<T> : IResult
    {
        T Data { get; }
    }
}