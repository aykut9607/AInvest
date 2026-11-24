using System.Net.Http.Json;
using System.Text.Json;
using FinanceProfile.Api.Application.Constants;
using FinanceProfile.Api.Application.Results;
using FinanceProfile.Api.DTOs;
using FinanceProfile.Api.Infrastructure.Abstract;
using Polly.CircuitBreaker;
using Polly.Timeout;


namespace FinanceProfile.Api.Infrastructure.External;

public class FinancialIqClient: IFinancialIqClient
{
    private readonly IHttpClientFactory  _httpClientFactory;

    public FinancialIqClient(IHttpClientFactory httpClientFactory)
    {
        _httpClientFactory = httpClientFactory;
    }

    public Task<IDataResult<FinancialIqCalculateResponse>> CalculateAsync(FinancialIqCalculateRequest request)
        => PostAsync<FinancialIqCalculateResponse>("/api/financial-iq/calculate", request,
            Messages.FinancialIqCalculationFailed, Messages.FinancialIqCalculated);

    public Task<IDataResult<JsonElement?>> GetDebtPayoffAsync(FinancialIqDebtPayoffRequest request)
        // successMessage null: keep IQ's message, it says why ("the payment does not cover the interest")
        => PostAsync<JsonElement?>("/api/financial-iq/debt-payoff", request,
            Messages.DebtPayoffFailed, successMessage: null);

    // one place for "call IQ and turn every way it can go wrong into a result" (same Polly pipeline for both calls)
    private async Task<IDataResult<T>> PostAsync<T>(string path, object body, string failedMessage, string? successMessage)
    {
        var client = _httpClientFactory.CreateClient("FinancialIqService");

        HttpResponseMessage response;
        try
        {
            response = await client.PostAsJsonAsync(path, body);
        }
        catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException
                                       or TimeoutRejectedException or BrokenCircuitException)
        {
            // IQ is down, did not answer in time (also after the retries) or the circuit breaker is open -
            // without this catch the caller would get a 500
            return new ErrorDataResult<T>(Messages.FinancialIqServiceUnavailable);
        }

        var wrapper = await ReadWrapperAsync<T>(response);
        if(!response.IsSuccessStatusCode)
        {
            // keep IQ's own reason (e.g. a validation message) when it sent one
            var failure = string.IsNullOrWhiteSpace(wrapper?.Message) ? failedMessage : wrapper.Message;
            return new ErrorDataResult<T>(failure);
        }

        // no wrapper, or a wrapper without data (a JsonElement "data": null counts as missing too)
        if (wrapper is null || wrapper.Data is not { } data
            || data is JsonElement { ValueKind: JsonValueKind.Null or JsonValueKind.Undefined })
        {
            return new ErrorDataResult<T>(Messages.FinancialIqEmptyResult);
        }

        var message = successMessage ?? (string.IsNullOrWhiteSpace(wrapper.Message) ? Messages.DebtPayoffCalculated : wrapper.Message);
        return new SuccessDataResult<T>(data, message);
    }

    // an error page or empty body from IQ must not throw here - it is treated as "no wrapper"
    private static async Task<IqServiceWrapper<T>?> ReadWrapperAsync<T>(HttpResponseMessage response)
    {
        try
        {
            return await response.Content.ReadFromJsonAsync<IqServiceWrapper<T>>();
        }
        catch (Exception ex) when (ex is JsonException or NotSupportedException)
        {
            return null;
        }
    }

    private class IqServiceWrapper<T>
    {
        public T? Data { get; set; }
        public bool Success { get; set; }
        public string? Message { get; set; }
    }
}
