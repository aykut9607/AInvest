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
            """{"data":{"score":88,"segment":"HIGH","factorBreakdown":"{\"factors\":{}}"},"success":true,"message":"ok"}"""));

        var result = await client.CalculateAsync(Request);

        Assert.True(result.Success);
        Assert.Equal(88, result.Data!.Score);
        Assert.Equal("HIGH", result.Data.Segment);
        Assert.Equal("""{"factors":{}}""", result.Data.FactorBreakdown);
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
