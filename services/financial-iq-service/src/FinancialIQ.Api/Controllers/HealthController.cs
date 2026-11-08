using FinancialIQ.Api.Infrastructure.EntityFramework;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace FinancialIQ.Api.Controllers;

[ApiController]
[Route("health")]
public class HealthController : ControllerBase
{
    private readonly FinancialIqDbContext  _context;

    public HealthController(FinancialIqDbContext  context)
    {
        _context = context;
    }

    [HttpGet]
    public IActionResult Get()
    {
        return Ok(new
        {
            service = "FinancialIQ.Api",
            status = "Healthy",
            timestamp = DateTime.UtcNow
        });
    }


    // proves the database answers; only the count is returned - health endpoints are unauthenticated,
    // so they must not list user ids (same rule as Finance Profile's db-check)
    [HttpGet("db-check")]
    public async Task<IActionResult> DbCheck()
    {
        var count = await _context.FinancialIqResults.CountAsync();
        return Ok(new { database = "reachable", resultCount = count });
    }
}