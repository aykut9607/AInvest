using System.Net.Http.Json;
using FinanceProfile.Api.Core.Utilities.Results;
using FinanceProfile.Api.DTOs;
using FinanceProfile.Api.Infrastructure.Abstract;


namespace FinanceProfile.Api.Infrastructure.External;

public class FinancialIqClient: IFinancialIqClient
{
    private readonly IHttpClientFactory  _httpClientFactory;

    public FinancialIqClient(IHttpClientFactory httpClientFactory)
    {
        _httpClientFactory = httpClientFactory;
    }

    public async Task<IDataResult<FinancialIqCalculateResponse>> CalculateAsync(FinancialIqCalculateRequest request)
    {
        var client = _httpClientFactory.CreateClient("FinancialIqService");
        var response = await client.PostAsJsonAsync("/api/financial-iq/calculate", request);
        if(!response.IsSuccessStatusCode)
        {
            return new ErrorDataResult<FinancialIqCalculateResponse>(null,"Failed to calculate financial IQ.");
        }

        var wrapper = await response.Content.ReadFromJsonAsync<IqServiceWrapper>();
        if (wrapper?.Data == null)//null-conditional operator .means that checking if wrapper is null .
        //if wapper is null ,then dont access the Data property and return null instead of throwing an exception
        {
            return new ErrorDataResult<FinancialIqCalculateResponse>("Financial IQ service returned an empty result.");
        }
        //if wrapper is not null ,then access the Data property and return it
        return new SuccessDataResult<FinancialIqCalculateResponse>(wrapper.Data,"Financial IQ calculation successful.");
    }

    private class IqServiceWrapper
    {
        public FinancialIqCalculateResponse? Data { get; set; }
        public bool Success { get; set; }
        public string? Message { get; set; }
    }
}