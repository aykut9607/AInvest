using Microsoft.Extensions.Http.Resilience;

namespace FinanceProfile.Api.Infrastructure.External;

// Polly policies (through Microsoft.Extensions.Http.Resilience) for every call Finance makes to Financial IQ.
// Order inside the pipeline: total timeout -> retry -> circuit breaker -> timeout per attempt.
public static class FinancialIqResilience
{
    public static IHttpClientBuilder AddFinancialIqResilience(
        this IHttpClientBuilder builder,
        Action<HttpStandardResilienceOptions>? overrides = null)
    {
        builder.AddStandardResilienceHandler(options =>
        {
            // timeout: one try may take at most 3 s, all tries together at most 10 s
            // (before this the HttpClient default was 100 s, so a hanging IQ blocked the request that long)
            options.AttemptTimeout.Timeout = TimeSpan.FromSeconds(3);
            options.TotalRequestTimeout.Timeout = TimeSpan.FromSeconds(10);

            // retry: 2 more tries on transient errors only (network error, timeout, 5xx, 408, 429),
            // waiting 0.3 s, then about 0.6 s (exponential backoff with jitter). A 400 from IQ is never retried.
            // POST /calculate is safe to repeat: MERGE writes the same latest result again; the only side effect
            // is a possible extra iq_history row when IQ saved but the answer was lost (an idempotency key fixes that later)
            options.Retry.MaxRetryAttempts = 2;
            options.Retry.Delay = TimeSpan.FromMilliseconds(300);

            // circuit breaker: if at least half of the last calls (min. 5 within 30 s) failed, stop calling IQ
            // for 15 s and fail at once; afterwards one trial call decides whether to close the circuit again
            options.CircuitBreaker.SamplingDuration = TimeSpan.FromSeconds(30);
            options.CircuitBreaker.MinimumThroughput = 5;
            options.CircuitBreaker.FailureRatio = 0.5;
            options.CircuitBreaker.BreakDuration = TimeSpan.FromSeconds(15);

            // tests use this to shorten the waits
            overrides?.Invoke(options);
        });

        return builder;
    }
}
