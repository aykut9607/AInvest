using FinanceProfile.Api.Infrastructure.EntityFramework;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;
using Polly.CircuitBreaker;
using Polly.Timeout;

namespace FinanceProfile.Api.Controllers;

[ApiController]
[Route("health")]
public class HealthController : ControllerBase
{
    private readonly FinanceDbContext _context;
    private readonly IHttpClientFactory _httpClientFactory;

    public HealthController(FinanceDbContext context, IHttpClientFactory httpClientFactory)
    {
        _context = context;
        _httpClientFactory = httpClientFactory; 
    }

    [HttpGet]
    public IActionResult Get()
    {
        return Ok(new
        {
            service = "FinanceProfile.Api",
            status = "Healthy",
            timestamp = DateTime.UtcNow 
        });
    }

    // proves the database answers; only the count is returned - health endpoints are unauthenticated,
    // so they must not list user ids
    [HttpGet("db-check")]
    public async Task<IActionResult> DbCheck()
    {
        var count = await _context.FinancialProfiles.CountAsync();
        return Ok(new { database = "reachable", profileCount = count });
    }

    [HttpGet("iq-check")]
    public async Task<IActionResult> IqCheck()
    {
       // same named client as the real IQ calls, so the base URL comes from FinancialIqService:BaseUrl in appsettings
       var client = _httpClientFactory.CreateClient("FinancialIqService");

       try
       {
           var response = await client.GetAsync("/health");
           //making a request to the Financial IQ service's health endpoint. It waits for the response asynchronously.Just like in JS.

           var content = await response.Content.ReadAsStringAsync();
           return Ok(new { financeCalledIq = true, iqStatusCode = (int)response.StatusCode, iqResponse = content });
       }
       // the named client goes through the Polly pipeline, so "IQ unreachable" can also arrive as a timeout
       // after the retries or as an open circuit - all of them mean 503 here, not a crash (500)
       catch (Exception ex) when (ex is HttpRequestException or TaskCanceledException
                                      or TimeoutRejectedException or BrokenCircuitException)
       {
           return StatusCode(StatusCodes.Status503ServiceUnavailable,
               new { financeCalledIq = false, iqBaseUrl = client.BaseAddress?.ToString(), error = ex.Message });
       }
    }
}