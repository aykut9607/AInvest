using System.Net;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.AspNetCore.TestHost;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;
using Yarp.ReverseProxy.Forwarder;

namespace EdgeGateway.Tests;

// starts the real gateway in memory, but instead of opening network connections YARP hands every forwarded
// request to a fake downstream that answers 200 and echoes where the request went. A test can therefore check
// which service and which path a URL reaches; a URL the gateway does not route or rejects never gets there.
public class GatewayFactory : WebApplicationFactory<Program>
{
    // the fake downstream copies the X-User-Id it received into this response header
    public const string SeenUserIdHeader = "X-Test-Seen-User-Id";

    protected override void ConfigureWebHost(Microsoft.AspNetCore.Hosting.IWebHostBuilder builder)
    {
        // host settings are visible while Program.cs runs, so the secret check at startup sees the test secret
        builder.UseSetting("Jwt:Secret", TestTokens.Secret);

        builder.ConfigureAppConfiguration((_, config) =>
        {
            config.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["ReverseProxy:Clusters:identity:Destinations:d1:Address"] = "http://identity.test/",
                ["ReverseProxy:Clusters:finance:Destinations:d1:Address"] = "http://finance.test/",
                ["ReverseProxy:Clusters:iq:Destinations:d1:Address"] = "http://iq.test/",
                ["ReverseProxy:Clusters:ai:Destinations:d1:Address"] = "http://ai.test/"
            });
        });

        builder.ConfigureTestServices(services =>
            services.AddSingleton<IForwarderHttpClientFactory, FakeDownstreamClientFactory>());
    }

    private sealed class FakeDownstreamClientFactory : IForwarderHttpClientFactory
    {
        public HttpMessageInvoker CreateClient(ForwarderHttpClientContext context) => new(new EchoHandler());
    }

    // body = "<METHOD> <full downstream url>", e.g. "GET http://finance.test/api/Profiles/u1"
    private sealed class EchoHandler : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            var response = new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent($"{request.Method} {request.RequestUri}")
            };
            if (request.Headers.TryGetValues("X-User-Id", out var userIds))
                response.Headers.Add(SeenUserIdHeader, userIds);
            return Task.FromResult(response);
        }
    }
}
