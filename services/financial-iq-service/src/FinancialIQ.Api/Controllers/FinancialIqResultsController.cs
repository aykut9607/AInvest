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

    // Query — debt payoff schedule (recursive CTE); computes, stores nothing. Called by Finance Profile with the
    // profile's debt and installment; not routed by the gateway (its IQ route is GET /{userId}/... only)
    [HttpPost("debt-payoff")]
    public async Task<IActionResult> DebtPayoff(DebtPayoffRequest request)
    {
        var result = await _queries.GetDebtPayoffAsync(request);

        if (!result.Success)
            return BadRequest(result);

        return Ok(result);
    }

    // Query — the IQ rule table: every scoring version with its rules (thresholds, points, warnings, special rules).
    // The same for every user; the gateway routes it to any logged-in user
    [HttpGet("scoring-rules")]
    public async Task<IActionResult> GetScoringRules()
        => Ok(await _queries.GetScoringRulesAsync());

    // Query — one version ("v1", "v2") or "current" (the active one)
    [HttpGet("scoring-rules/{version}")]
    public async Task<IActionResult> GetScoringRules(string version)
    {
        var result = await _queries.GetScoringRulesAsync(version);

        if (!result.Success)
            return NotFound(result);

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