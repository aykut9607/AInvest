using FinanceProfile.Api.Controllers;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using Polly.CircuitBreaker;
using Polly.Timeout;

namespace FinanceProfile.Tests;

// iq-check must report an unreachable IQ as 503 for every way the Polly pipeline can say "unreachable"
public class HealthControllerTests
{
    public static TheoryData<Exception> UnreachableIq => new()
    {
        new HttpRequestException("connection refused"),
        new TaskCanceledException("timeout"),
        new TimeoutRejectedException("attempt timed out"),
        new BrokenCircuitException("circuit is open")
    };

    [Theory]
    [MemberData(nameof(UnreachableIq))]
    public async Task IqCheck_IqUnreachable_Returns503(Exception failure)
    {
        // iq-check does not touch the database, so no DbContext is needed
        var controller = new HealthController(null!, new ThrowingClientFactory(failure));

        var response = await controller.IqCheck();

        var result = Assert.IsType<ObjectResult>(response);
        Assert.Equal(StatusCodes.Status503ServiceUnavailable, result.StatusCode);
    }

    private sealed class ThrowingClientFactory(Exception failure) : IHttpClientFactory
    {
        public HttpClient CreateClient(string name) =>
            new(new ThrowingHandler(failure)) { BaseAddress = new Uri("http://iq.test") };
    }

    private sealed class ThrowingHandler(Exception failure) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => throw failure;
    }
}
