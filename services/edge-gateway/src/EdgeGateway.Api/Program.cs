using EdgeGateway.Api.Middleware;

var builder = WebApplication.CreateBuilder(args);

// YARP reads the routes and clusters from appsettings.json ("ReverseProxy" section)
builder.Services.AddReverseProxy()
    .LoadFromConfig(builder.Configuration.GetSection("ReverseProxy"));

var app = builder.Build();

app.UseMiddleware<CorrelationIdMiddleware>();

// the gateway's own liveness check; everything else is forwarded
app.MapGet("/health", () => Results.Ok(new { service = "EdgeGateway.Api", status = "Healthy", timestamp = DateTime.UtcNow }));

app.MapReverseProxy();

app.Run();

// lets WebApplicationFactory<Program> start the gateway in the tests
public partial class Program { }
