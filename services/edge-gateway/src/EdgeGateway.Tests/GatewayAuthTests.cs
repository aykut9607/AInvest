using System.Net;

namespace EdgeGateway.Tests;

// JWT validation at the edge (401 = who are you?) and the same-user rule (403 = not yours)
public class GatewayAuthTests : IClassFixture<GatewayFactory>
{
    private const string OwnProfile = "/api/Profiles/u1";

    private readonly HttpClient _client;

    public GatewayAuthTests(GatewayFactory factory)
    {
        _client = factory.CreateClient();
    }

    [Fact]
    public async Task NoToken_Is401()
    {
        var response = await _client.SendAsync(TestTokens.Get(OwnProfile));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task TokenSignedWithAnotherKey_Is401()
    {
        var forged = TestTokens.Create("u1", secret: "attacker-secret-key-that-is-also-long-enough-for-hs512-0987654321!!");

        var response = await _client.SendAsync(TestTokens.Get(OwnProfile, forged));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task ExpiredToken_Is401()
    {
        var expired = TestTokens.Create("u1", expires: DateTime.UtcNow.AddMinutes(-5));

        var response = await _client.SendAsync(TestTokens.Get(OwnProfile, expired));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("some-other-issuer", TestTokens.Audience)]
    [InlineData(TestTokens.Issuer, "some-other-api")]
    public async Task TokenFromAnotherSystem_Is401(string issuer, string audience)
    {
        var token = TestTokens.Create("u1", issuer: issuer, audience: audience);

        var response = await _client.SendAsync(TestTokens.Get(OwnProfile, token));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Fact]
    public async Task UnsignedAlgNoneToken_Is401()
    {
        var response = await _client.SendAsync(TestTokens.Get(OwnProfile, TestTokens.Unsigned("u1")));

        Assert.Equal(HttpStatusCode.Unauthorized, response.StatusCode);
    }

    [Theory]
    [InlineData("/api/Profiles/u2")]
    [InlineData("/api/Profiles/u2/calculate-iq")]
    [InlineData("/api/financial-iq/u2/latest")]
    public async Task ValidTokenForAnotherUser_Is403(string otherUsersPath)
    {
        var response = await _client.SendAsync(TestTokens.Get(otherUsersPath, TestTokens.Create("u1")));

        Assert.Equal(HttpStatusCode.Forbidden, response.StatusCode);
    }

    [Fact]
    public async Task AuthRoutes_NeedNoToken()
    {
        var response = await _client.SendAsync(TestTokens.Get("/auth/register"));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
    }

    [Fact]
    public async Task DownstreamGetsTheUserIdFromTheToken_NotFromTheClient()
    {
        var request = TestTokens.Get(OwnProfile, TestTokens.Create("u1"));
        // the client tries to pretend to be someone else
        request.Headers.Add("X-User-Id", "u2");

        var response = await _client.SendAsync(request);

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal("u1", response.Headers.GetValues(GatewayFactory.SeenUserIdHeader).Single());
    }
}
