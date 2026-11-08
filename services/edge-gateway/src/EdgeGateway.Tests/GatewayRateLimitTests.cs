using System.Net;

namespace EdgeGateway.Tests;

// login brute-force protection: 5 attempts per IP per minute (appsettings), the 6th is refused at the gateway.
// Its own class (and so its own gateway instance), because the login counter would otherwise be shared.
public class GatewayRateLimitTests : IClassFixture<GatewayFactory>
{
    private readonly HttpClient _client;

    public GatewayRateLimitTests(GatewayFactory factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task SixthLoginInAMinute_Is429_WithRetryAfter()
    {
        for (var attempt = 1; attempt <= 5; attempt++)
        {
            var allowed = await PostLogin();
            Assert.Equal(HttpStatusCode.OK, allowed.StatusCode);
        }

        var refused = await PostLogin();

        Assert.Equal(HttpStatusCode.TooManyRequests, refused.StatusCode);
        Assert.NotNull(refused.Headers.RetryAfter);
    }

    [Fact]
    public async Task OtherAuthEndpoints_AreNotCountedAsLoginAttempts()
    {
        for (var attempt = 1; attempt <= 10; attempt++)
        {
            var response = await _client.PostAsync("/auth/refresh", new StringContent("{}"));
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        }
    }

    private Task<HttpResponseMessage> PostLogin() =>
        _client.PostAsync("/auth/login", new StringContent("{\"email\":\"a@b.c\",\"password\":\"wrong\"}"));
}
