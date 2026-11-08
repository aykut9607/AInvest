using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Domain.Dtos;
using Microsoft.AspNetCore.Mvc;

namespace FinancialIQ.Api.Controllers;

[Route("api/financial-iq")]
[ApiController]
public class FinancialIqResultsController : ControllerBase
{
    // CQRS-lite: writes go to the command service, reads to the query service
    private readonly IFinancialIqCommandService _commands;
    private readonly IFinancialIqQueryService _queries;

    public FinancialIqResultsController(IFinancialIqCommandService commands, IFinancialIqQueryService queries)
    {
        _commands = commands;
        _queries = queries;
    }

    // Command — calculates and saves the score
    [HttpPost("calculate")]
    public async Task<IActionResult> Calculate(CalculateRequest request)
    {
        var result = await _commands.CalculateAsync(request);

        if (!result.Success)
            return BadRequest(result);

        return Ok(result);
    }

    // Query — only reads the latest saved result
    [HttpGet("{userId}/latest")]
    public async Task<IActionResult> GetLatest(string userId)
    {
        var result = await _queries.GetLatestAsync(userId);

        if (!result.Success)
            return result.Message == Messages.FinancialIqResultNotFound
                ? NotFound(result)
                : BadRequest(result);

        return Ok(result);
    }

    // Query — score history for a trend chart, oldest first
    [HttpGet("{userId}/history")]
    public async Task<IActionResult> GetHistory(string userId, [FromQuery] int take = 12)
    {
        var result = await _queries.GetHistoryAsync(userId, take);

        if (!result.Success)
            return result.Message == Messages.FinancialIqHistoryNotFound
                ? NotFound(result)
                : BadRequest(result);

        return Ok(result);
    }
}