using System.Net;
using System.Text;
using FinanceProfile.Api.Application.Constants;
using FinanceProfile.Api.DTOs;
using FinanceProfile.Api.Infrastructure.External;

namespace FinanceProfile.Tests;

// the IQ service is replaced by a fake HTTP handler, so these tests need no running service
public class FinancialIqClientTests
{
    private static FinancialIqClient ClientReturning(Func<HttpRequestMessage, HttpResponseMessage> respond)
        => new(new StubHttpClientFactory(new StubHandler(respond)));

    private static HttpResponseMessage Json(HttpStatusCode status, string body)
        => new(status) { Content = new StringContent(body, Encoding.UTF8, "application/json") };

    private static readonly FinancialIqCalculateRequest Request = new() { UserId = "u1", MonthlyIncome = 10000 };

    [Fact]
    public async Task IqUnreachable_ReturnsUnavailableMessage_InsteadOfThrowing()
    {
        var client = ClientReturning(_ => throw new HttpRequestException("connection refused"));

        var result = await client.CalculateAsync(Request);

        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqServiceUnavailable, result.Message);
    }

    [Fact]
    public async Task IqTimesOut_ReturnsUnavailableMessage()
    {
        var client = ClientReturning(_ => throw new TaskCanceledException("timeout"));

        var result = await client.CalculateAsync(Request);

        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqServiceUnavailable, result.Message);
    }

    [Fact]
    public async Task IqRejectsRequest_KeepsIqsOwnMessage()
    {
        var client = ClientReturning(_ => Json(HttpStatusCode.BadRequest,
            """{"data":null,"success":false,"message":"Impatience level must be between 1 and 5."}"""));

        var result = await client.CalculateAsync(Request);

        Assert.False(result.Success);
        Assert.Equal("Impatience level must be between 1 and 5.", result.Message);
    }

    [Fact]
    public async Task IqReturnsNonJsonError_ReturnsGenericFailure_InsteadOfThrowing()
    {
        var client = ClientReturning(_ => new HttpResponseMessage(HttpStatusCode.InternalServerError)
        {
            Content = new StringContent("<html>boom</html>", Encoding.UTF8, "text/html")
        });

        var result = await client.CalculateAsync(Request);

        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqCalculationFailed, result.Message);
    }

    [Fact]
    public async Task IqSucceeds_ReturnsScoreSegmentAndBreakdown()
    {
        var client = ClientReturning(_ => Json(HttpStatusCode.OK,
            """{"data":{"score":88,"segment":"HIGH","factorBreakdown":{"version":"v2","factors":{}}},"success":true,"message":"ok"}"""));

        var result = await client.CalculateAsync(Request);

        Assert.True(result.Success);
        Assert.Equal(88, result.Data!.Score);
        Assert.Equal("HIGH", result.Data.Segment);
        // passed through as a JSON object (contract v2)
        Assert.Equal(System.Text.Json.JsonValueKind.Object, result.Data.FactorBreakdown.ValueKind);
        Assert.Equal("v2", result.Data.FactorBreakdown.GetProperty("version").GetString());
    }

    private static readonly FinancialIqDebtPayoffRequest PayoffRequest = new() { TotalDebt = 10000, MonthlyPayment = 1000 };

    [Fact]
    public async Task DebtPayoff_PostsToIqsEndpoint_AndPassesTheScheduleAndMessageOn()
    {
        string? calledPath = null;
        var client = ClientReturning(request =>
        {
            calledPath = request.RequestUri!.AbsolutePath;
            return Json(HttpStatusCode.OK,
                """{"data":{"paidOff":false,"months":null,"schedule":[]},"success":true,"message":"The monthly payment does not cover the monthly interest, so the debt never gets smaller."}""");
        });

        var result = await client.GetDebtPayoffAsync(PayoffRequest);

        Assert.Equal("/api/financial-iq/debt-payoff", calledPath);
        Assert.True(result.Success);
        Assert.False(result.Data!.Value.GetProperty("paidOff").GetBoolean());
        // IQ's reason reaches the client
        Assert.StartsWith("The monthly payment does not cover", result.Message);
    }

    [Fact]
    public async Task DebtPayoff_IqUnreachable_ReturnsUnavailableMessage()
    {
        var client = ClientReturning(_ => throw new HttpRequestException("connection refused"));

        var result = await client.GetDebtPayoffAsync(PayoffRequest);

        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqServiceUnavailable, result.Message);
    }

    [Fact]
    public async Task DebtPayoff_SuccessWithoutData_IsAnEmptyResult()
    {
        var client = ClientReturning(_ => Json(HttpStatusCode.OK, """{"data":null,"success":true,"message":"ok"}"""));

        var result = await client.GetDebtPayoffAsync(PayoffRequest);

        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqEmptyResult, result.Message);
    }

    [Fact]
    public async Task Calculate_KeepsItsOwnSuccessMessage()
    {
        var client = ClientReturning(_ => Json(HttpStatusCode.OK,
            """{"data":{"score":88,"segment":"HIGH","factorBreakdown":{}},"success":true,"message":"Financial IQ score calculated successfully."}"""));

        var result = await client.CalculateAsync(Request);

        Assert.Equal(Messages.FinancialIqCalculated, result.Message);
    }

    private sealed class StubHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => Task.FromResult(respond(request));
    }

    private sealed class StubHttpClientFactory(HttpMessageHandler handler) : IHttpClientFactory
    {
        public HttpClient CreateClient(string name) => new(handler) { BaseAddress = new Uri("http://iq.test") };
    }
}
