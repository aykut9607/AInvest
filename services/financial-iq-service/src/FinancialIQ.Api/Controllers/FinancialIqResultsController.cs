using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Domain.Dtos;
using Microsoft.AspNetCore.Mvc;

namespace FinancialIQ.Api.Controllers;

[Route("api/financial-iq")]
[ApiController]
public class FinancialIqResultsController : ControllerBase
{
    private readonly IFinancialIqResultService _service;

    public FinancialIqResultsController(IFinancialIqResultService service)
    {
        _service = service;
    }

    // Command — calculates and saves the score
    [HttpPost("calculate")]
    public async Task<IActionResult> Calculate(CalculateRequest request)
    {
        var result = await _service.CalculateAsync(request);

        if (!result.Success)
            return BadRequest(result);

        return Ok(result);
    }

    // Query — only reads the latest saved result
    [HttpGet("{userId}/latest")]
    public async Task<IActionResult> GetLatest(string userId)
    {
        var result = await _service.GetLatestAsync(userId);

        if (!result.Success)
            return NotFound(result);

        return Ok(result);
    }
}