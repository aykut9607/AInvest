using System.Text;
using System.Threading.RateLimiting;
using EdgeGateway.Api.Middleware;
using Microsoft.AspNetCore.Authentication.JwtBearer;
using Microsoft.IdentityModel.Tokens;
using Yarp.ReverseProxy.Transforms;

var builder = WebApplication.CreateBuilder(args);

var jwt = builder.Configuration.GetSection("Jwt");
// no fallback secret on purpose: without the real one the gateway must not start (a default would be a backdoor)
var secret = jwt["Secret"];
if (string.IsNullOrWhiteSpace(secret))
    throw new InvalidOperationException("Jwt:Secret is missing. Set it with: dotnet user-secrets set \"Jwt:Secret\" \"<same value as Identity's JWT_SECRET>\"");

builder.Services.AddAuthentication(JwtBearerDefaults.AuthenticationScheme)
    .AddJwtBearer(options =>
    {
        // keep the token's claim names as they are ("sub" stays "sub" instead of a long .NET claim type)
        options.MapInboundClaims = false;
        options.TokenValidationParameters = new TokenValidationParameters
        {
            ValidateIssuer = true,
            ValidIssuer = jwt["Issuer"],
            ValidateAudience = true,
            ValidAudience = jwt["Audience"],
            ValidateLifetime = true,
            // default allowance is 5 minutes; an expired access token should stop working almost immediately
            ClockSkew = TimeSpan.FromSeconds(30),
            ValidateIssuerSigningKey = true,
            // same bytes as Identity: Keys.hmacShaKeyFor(secret.getBytes(UTF_8))
            IssuerSigningKey = new SymmetricSecurityKey(Encoding.UTF8.GetBytes(secret)),
            // only the algorithm Identity uses; closes the door to "alg: none" and algorithm-switching tricks
            ValidAlgorithms = [SecurityAlgorithms.HmacSha512]
        };
    });

builder.Services.AddAuthorization(options =>
{
    // BOLA protection (OWASP API1): a valid token is not enough, the {userId} in the URL must be the caller's own.
    // Without this, user A could read user B's profile just by changing the id in the address.
    options.AddPolicy("sameUser", policy => policy
        .RequireAuthenticatedUser()
        .RequireAssertion(context =>
            context.Resource is HttpContext http &&
            http.GetRouteValue("userId") is string userIdInUrl &&
            userIdInUrl == context.User.FindFirst("sub")?.Value));
});

// brute-force protection for the login endpoint (the route uses RateLimiterPolicy "login" in appsettings.json):
// at most N attempts per client IP per window; the next one gets 429 before it ever reaches Identity
var loginLimit = builder.Configuration.GetSection("RateLimiting:Login");
builder.Services.AddRateLimiter(options =>
{
    options.RejectionStatusCode = StatusCodes.Status429TooManyRequests;

    options.AddPolicy("login", httpContext =>
        RateLimitPartition.GetFixedWindowLimiter(
            // one counter per caller IP
            partitionKey: httpContext.Connection.RemoteIpAddress?.ToString() ?? "unknown",
            factory: _ => new FixedWindowRateLimiterOptions
            {
                PermitLimit = loginLimit.GetValue("PermitLimit", 5),
                Window = TimeSpan.FromSeconds(loginLimit.GetValue("WindowSeconds", 60)),
                // reject at once instead of making the extra attempts wait in a queue
                QueueLimit = 0
            }));

    // tell the client how long to wait before trying again
    options.OnRejected = (context, _) =>
    {
        if (context.Lease.TryGetMetadata(MetadataName.RetryAfter, out var retryAfter))
            context.HttpContext.Response.Headers.RetryAfter = ((int)retryAfter.TotalSeconds).ToString();
        return ValueTask.CompletedTask;
    };
});

// YARP reads the routes and clusters from appsettings.json ("ReverseProxy" section)
builder.Services.AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"))
    .AddTransforms(transforms => transforms.AddRequestTransform(context =>
    {
        // services behind the gateway learn who the caller is from X-User-Id. A client could send that header
        // itself, so it is always removed and, for a validated token, set again from the token's "sub"
        context.ProxyRequest.Headers.Remove(UserIdHeader.Name);
        var userId = context.HttpContext.User.FindFirst("sub")?.Value;
        if (userId is not null)
            context.ProxyRequest.Headers.Add(UserIdHeader.Name, userId);
        return ValueTask.CompletedTask;
    }));

var app = builder.Build();

app.UseMiddleware<CorrelationIdMiddleware>();

// order matters: first find out who the caller is, then check what they may do, then forward
app.UseAuthentication();
app.UseAuthorization();
app.UseRateLimiter();

// the gateway's own liveness check; everything else is forwarded
app.MapGet("/health", () => Results.Ok(new { service = "EdgeGateway.Api", status = "Healthy", timestamp = DateTime.UtcNow }));

app.MapReverseProxy();

app.Run();

// lets WebApplicationFactory<Program> start the gateway in the tests
public partial class Program { }

public static class UserIdHeader
{
    public const string Name = "X-User-Id";
}
