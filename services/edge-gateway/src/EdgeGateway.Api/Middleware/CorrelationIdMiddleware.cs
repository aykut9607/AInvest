using System.Text.RegularExpressions;

namespace EdgeGateway.Api.Middleware;

// gives every request one id that travels to the downstream service (YARP forwards request headers)
// and comes back in the response, so the same request can be followed across gateway, Finance and IQ logs
public partial class CorrelationIdMiddleware
{
    public const string HeaderName = "X-Correlation-ID";

    private readonly RequestDelegate _next;

    public CorrelationIdMiddleware(RequestDelegate next)
    {
        _next = next;
    }

    public async Task InvokeAsync(HttpContext context)
    {
        // the caller's id is kept only if it looks like an id: it ends up in every service's logs,
        // so a very long or odd value (log injection, log flooding) is replaced by a fresh one here at the edge
        var correlationId = context.Request.Headers[HeaderName].FirstOrDefault();
        if (correlationId is null || !SafeId().IsMatch(correlationId))
            correlationId = Guid.NewGuid().ToString();

        context.Request.Headers[HeaderName] = correlationId;

        context.Response.OnStarting(() =>
        {
            context.Response.Headers[HeaderName] = correlationId;
            return Task.CompletedTask;
        });

        await _next(context);
    }

    // letters, digits, '-', '_' and '.', 1 to 64 characters (a GUID is 36)
    [GeneratedRegex("^[A-Za-z0-9._-]{1,64}$")]
    private static partial Regex SafeId();
}
