using System.Net;

namespace EdgeGateway.Tests;

// which URLs the gateway forwards (and to which service) and which it keeps closed
public class GatewayRoutingTests : IClassFixture<GatewayFactory>
{
    private readonly HttpClient _client;

    public GatewayRoutingTests(GatewayFactory factory)
    {
        _client = factory.CreateClient();
    }

    [Theory]
    [InlineData("/auth/login", "http://identity.test/auth/login")]
    [InlineData("/api/Profiles/u1", "http://finance.test/api/Profiles/u1")]
    [InlineData("/api/Profiles/u1/calculate-iq", "http://finance.test/api/Profiles/u1/calculate-iq")]
    [InlineData("/api/financial-iq/u1/latest", "http://iq.test/api/financial-iq/u1/latest")]
    [InlineData("/api/financial-iq/u1/history?take=5", "http://iq.test/api/financial-iq/u1/history?take=5")]
    [InlineData("/ai/explain-financial-iq", "http://ai.test/ai/explain-financial-iq")]
    public async Task PublicRoute_IsForwardedToTheRightService(string path, string expectedDownstreamUrl)
    {
        var response = await _client.SendAsync(TestTokens.Get(path, TestTokens.Create("u1")));

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.Equal($"GET {expectedDownstreamUrl}", await response.Content.ReadAsStringAsync());
    }

    [Fact]
    public async Task ListingAllProfiles_IsNotReachableThroughTheGateway()
    {
        var response = await _client.SendAsync(TestTokens.Get("/api/Profiles", TestTokens.Create("u1")));

        Assert.Equal(HttpStatusCode.NotFound, response.StatusCode);
    }

    [Fact]
    public async Task InternalIqCalculate_IsNotReachableThroughTheGateway()
    {
        var request = new HttpRequestMessage(HttpMethod.Post, "/api/financial-iq/calculate")
        {
            Content = new StringContent("{}")
        };
        request.Headers.Authorization = new("Bearer", TestTokens.Create("u1"));

        var response = await _client.SendAsync(request);

        // the IQ route only accepts GET, so this POST never reaches the fake downstream
        Assert.False(response.IsSuccessStatusCode);
    }

    [Fact]
    public async Task EveryResponse_CarriesACorrelationId()
    {
        var response = await _client.GetAsync("/health");

        Assert.Equal(HttpStatusCode.OK, response.StatusCode);
        Assert.True(response.Headers.Contains("X-Correlation-ID"));
    }

    [Fact]
    public async Task CallersCorrelationId_IsKept()
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/health");
        request.Headers.Add("X-Correlation-ID", "test-123");

        var response = await _client.SendAsync(request);

        Assert.Equal("test-123", response.Headers.GetValues("X-Correlation-ID").Single());
    }

    [Theory]
    [InlineData("has spaces and <script>")]
    [InlineData("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")]
    public async Task UnsafeCorrelationId_IsReplacedWithAFreshOne(string unsafeId)
    {
        var request = new HttpRequestMessage(HttpMethod.Get, "/health");
        request.Headers.TryAddWithoutValidation("X-Correlation-ID", unsafeId);

        var response = await _client.SendAsync(request);

        var returned = response.Headers.GetValues("X-Correlation-ID").Single();
        Assert.NotEqual(unsafeId, returned);
        Assert.True(Guid.TryParse(returned, out _));
    }

    [Fact]
    public async Task BrowserPreflightFromTheReactOrigin_IsAllowed_WithoutAToken()
    {
        var preflight = new HttpRequestMessage(HttpMethod.Options, "/api/Profiles/u1");
        preflight.Headers.Add("Origin", "http://localhost:5173");
        preflight.Headers.Add("Access-Control-Request-Method", "PUT");
        preflight.Headers.Add("Access-Control-Request-Headers", "authorization,content-type");

        var response = await _client.SendAsync(preflight);

        Assert.True(response.IsSuccessStatusCode);
        Assert.Equal("http://localhost:5173", response.Headers.GetValues("Access-Control-Allow-Origin").Single());
    }

    [Fact]
    public async Task BrowserPreflightFromAnUnknownOrigin_GetsNoCorsPermission()
    {
        var preflight = new HttpRequestMessage(HttpMethod.Options, "/api/Profiles/u1");
        preflight.Headers.Add("Origin", "http://evil.example");
        preflight.Headers.Add("Access-Control-Request-Method", "PUT");

        var response = await _client.SendAsync(preflight);

        Assert.False(response.Headers.Contains("Access-Control-Allow-Origin"));
    }
}
