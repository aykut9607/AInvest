using System.Net.Http.Json;
using FinanceProfile.Api.Application.Constants;
using FinanceProfile.Api.Application.Results;
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

        HttpResponseMessage response;
        try
        {
            response = await client.PostAsJsonAsync("/api/financial-iq/calculate", request);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException)
        {
            // IQ is down or did not answer in time - without this catch the caller would get a 500
            return new ErrorDataResult<FinancialIqCalculateResponse>(Messages.FinancialIqServiceUnavailable);
        }

        var wrapper = await ReadWrapperAsync(response);
        if(!response.IsSuccessStatusCode)
        {
            // keep IQ's own reason (e.g. a validation message) when it sent one
            var message = string.IsNullOrWhiteSpace(wrapper?.Message) ? Messages.FinancialIqCalculationFailed : wrapper.Message;
            return new ErrorDataResult<FinancialIqCalculateResponse>(message);
        }

        if (wrapper?.Data == null)//null-conditional operator .means that checking if wrapper is null .
        //if wapper is null ,then dont access the Data property and return null instead of throwing an exception
        {
            return new ErrorDataResult<FinancialIqCalculateResponse>(Messages.FinancialIqEmptyResult);
        }
        //if wrapper is not null ,then access the Data property and return it
        return new SuccessDataResult<FinancialIqCalculateResponse>(wrapper.Data, Messages.FinancialIqCalculated);
    }

    // an error page or empty body from IQ must not throw here - it is treated as "no wrapper"
    private static async Task<IqServiceWrapper?> ReadWrapperAsync(HttpResponseMessage response)
    {
        try
        {
            return await response.Content.ReadFromJsonAsync<IqServiceWrapper>();
        }
        catch (Exception ex) when (ex is System.Text.Json.JsonException or NotSupportedException)
        {
            return null;
        }
    }

    private class IqServiceWrapper
    {
        public FinancialIqCalculateResponse? Data { get; set; }
        public bool Success { get; set; }
        public string? Message { get; set; }
    }
}
