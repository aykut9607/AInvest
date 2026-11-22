using System.Net;

namespace EdgeGateway.Tests;

// /ai/** budget: 10 requests per user per minute (appsettings), the 11th is refused at the gateway so the local LLM
// is never asked. Own class (and so its own gateway instance); every test uses its own user ids, because the
// counters live for the whole minute and would otherwise leak from one test into the next.
public class GatewayAiRateLimitTests : IClassFixture<GatewayFactory>
{
    private const int AiLimit = 10;

    private readonly HttpClient _client;

    public GatewayAiRateLimitTests(GatewayFactory factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task EleventhAiRequestInAMinute_Is429_WithRetryAfter()
    {
        for (var attempt = 1; attempt <= AiLimit; attempt++)
        {
            var allowed = await PostExplain("ai-user-a");
            Assert.Equal(HttpStatusCode.OK, allowed.StatusCode);
        }

        var refused = await PostExplain("ai-user-a");

        Assert.Equal(HttpStatusCode.TooManyRequests, refused.StatusCode);
        Assert.NotNull(refused.Headers.RetryAfter);
    }

    [Fact]
    public async Task OneUsersLimit_DoesNotBlockAnotherUser()
    {
        for (var attempt = 1; attempt <= AiLimit + 1; attempt++)
            await PostExplain("ai-user-b");

        var otherUser = await PostExplain("ai-user-c");

        Assert.Equal(HttpStatusCode.OK, otherUser.StatusCode);
    }

    [Fact]
    public async Task OtherRoutes_AreNotCountedAgainstTheAiBudget()
    {
        for (var attempt = 1; attempt <= AiLimit + 5; attempt++)
        {
            var response = await _client.SendAsync(
                TestTokens.Get("/api/Profiles/ai-user-d", TestTokens.Create("ai-user-d")));
            Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        }

        var ai = await PostExplain("ai-user-d");

        Assert.Equal(HttpStatusCode.OK, ai.StatusCode);
    }

    [Fact]
    public async Task RequestWithoutAToken_Is401_NotCounted()
    {
        // the token check runs before the rate limiter: anonymous callers are rejected without using any budget
        for (var attempt = 1; attempt <= AiLimit + 5; attempt++)
        {
            var anonymous = await _client.PostAsync("/ai/explain-financial-iq", new StringContent("{}"));
            Assert.Equal(HttpStatusCode.Unauthorized, anonymous.StatusCode);
        }
    }

    private Task<HttpResponseMessage> PostExplain(string userId)
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/ai/explain-financial-iq")
        {
            Content = new StringContent("{\"score\":62,\"segment\":\"MEDIUM\"}")
        };
        request.Headers.Authorization = new("Bearer", TestTokens.Create(userId));
        return _client.SendAsync(request);
    }
}
