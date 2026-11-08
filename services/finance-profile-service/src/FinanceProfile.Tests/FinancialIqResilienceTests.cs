using System.Net;
using System.Text;
using FinanceProfile.Api.Application.Constants;
using FinanceProfile.Api.DTOs;
using FinanceProfile.Api.Infrastructure.External;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Http.Resilience;

namespace FinanceProfile.Tests;

// the real HttpClient pipeline with the real Polly policies (AddFinancialIqResilience); only IQ itself is a fake
// that counts how often it was called. Waits are shortened so the tests run in milliseconds.
public class FinancialIqResilienceTests
{
    private const string SuccessBody =
        """{"data":{"score":72,"segment":"HIGH","factorBreakdown":"{}"},"success":true,"message":"ok"}""";

    private static readonly FinancialIqCalculateRequest Request = new() { UserId = "u1", MonthlyIncome = 10000 };

    [Fact]
    public async Task TransientErrors_AreRetried_UntilIqAnswers()
    {
        // IQ fails twice with 503, then answers
        var iq = new FakeIq(attempt => attempt <= 2 ? Status(HttpStatusCode.ServiceUnavailable) : Json(HttpStatusCode.OK, SuccessBody));

        var result = await ClientFor(iq).CalculateAsync(Request);

        Assert.True(result.Success);
        Assert.Equal(72, result.Data!.Score);
        Assert.Equal(3, iq.Attempts);
    }

    [Fact]
    public async Task ValidationError_IsNotRetried()
    {
        var iq = new FakeIq(_ => Json(HttpStatusCode.BadRequest,
            """{"data":null,"success":false,"message":"Impatience level must be between 1 and 5."}"""));

        var result = await ClientFor(iq).CalculateAsync(Request);

        // a 400 will not get better by asking again, so IQ is called exactly once
        Assert.Equal(1, iq.Attempts);
        Assert.Equal("Impatience level must be between 1 and 5.", result.Message);
    }

    [Fact]
    public async Task HangingIq_TimesOut_AndReturnsUnavailable()
    {
        var iq = new FakeIq(_ => Json(HttpStatusCode.OK, SuccessBody), delay: TimeSpan.FromSeconds(10));

        var started = DateTime.UtcNow;
        var result = await ClientFor(iq, o =>
        {
            o.AttemptTimeout.Timeout = TimeSpan.FromMilliseconds(100);
            o.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(2);
        }).CalculateAsync(Request);

        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqServiceUnavailable, result.Message);
        // 1 try + 2 retries, each cut at 100 ms, instead of waiting 10 s (or the old 100 s default)
        Assert.Equal(3, iq.Attempts);
        Assert.True(DateTime.UtcNow - started < TimeSpan.FromSeconds(2));
    }

    [Fact]
    public async Task AfterRepeatedFailures_CircuitOpens_AndIqIsNoLongerCalled()
    {
        var iq = new FakeIq(_ => Status(HttpStatusCode.InternalServerError));
        var client = ClientFor(iq);

        // first calls: every attempt fails until the breaker has seen 5 failures and opens
        await client.CalculateAsync(Request);
        await client.CalculateAsync(Request);
        var attemptsWhenOpened = iq.Attempts;

        var result = await client.CalculateAsync(Request);

        // the open circuit answers at once: IQ is not called again, Finance gets a clear "unavailable"
        Assert.Equal(attemptsWhenOpened, iq.Attempts);
        Assert.False(result.Success);
        Assert.Equal(Messages.FinancialIqServiceUnavailable, result.Message);
    }

    private static FinancialIqClient ClientFor(FakeIq iq, Action<HttpStandardResilienceOptions>? overrides = null)
    {
        var services = new ServiceCollection();
        services.AddHttpClient("FinancialIqService", c => c.BaseAddress = new Uri("http://iq.test"))
            .ConfigurePrimaryHttpMessageHandler(() => new FakeIqHandler(iq))
            .AddFinancialIqResilience(o =>
            {
                o.Retry.Delay = TimeSpan.Zero;
                overrides?.Invoke(o);
            });

        var factory = services.BuildServiceProvider().GetRequiredService<IHttpClientFactory>();
        return new FinancialIqClient(factory);
    }

    private static HttpResponseMessage Status(HttpStatusCode status) => new(status);

    private static HttpResponseMessage Json(HttpStatusCode status, string body)
        => new(status) { Content = new StringContent(body, Encoding.UTF8, "application/json") };

    // what IQ answers on the n-th attempt (1-based), optionally after a delay
    private sealed class FakeIq(Func<int, HttpResponseMessage> respond, TimeSpan? delay = null)
    {
        private int _attempts;
        public int Attempts => _attempts;

        public async Task<HttpResponseMessage> AnswerAsync(CancellationToken cancellationToken)
        {
            var attempt = Interlocked.Increment(ref _attempts);
            if (delay is not null)
                await Task.Delay(delay.Value, cancellationToken);
            return respond(attempt);
        }
    }

    private sealed class FakeIqHandler(FakeIq iq) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
            => iq.AnswerAsync(cancellationToken);
    }
}
