using FinanceProfile.Api.Application.Abstract;
using FinanceProfile.Api.Domain.Entities;
using FinanceProfile.Api.DTOs;
using Microsoft.AspNetCore.Mvc;

namespace FinanceProfile.Api.Controllers;

[Route("api/[controller]")]
[ApiController]
public class ProfilesController : ControllerBase
{
    private readonly IFinancialProfileService _financialProfileService;

    public ProfilesController(IFinancialProfileService financialProfileService)
    {
        _financialProfileService = financialProfileService;
    }

    [HttpGet]
    public async Task<IActionResult> GetAll()
    {
        var result = await _financialProfileService.GetAllAsync();

        if (!result.Success)
        {
            return BadRequest(result);
        }

        return Ok(result);
    }

    [HttpGet("{userId}")]
    public async Task <IActionResult> GetByUserId(string userId)
    {
      var result = await _financialProfileService.GetByUserIdAsync(userId);
      if(!result.Success)
      {
        return NotFound(result);
      }
      return Ok(result);

    }

    [HttpPut("{userId}")]
    public async Task<IActionResult> Upsert(string userId,UpsertFinancialProfileRequest request)
    {
        var result = await _financialProfileService.UpsertAsync(userId, request);

        if (!result.Success)
        {
            return BadRequest(result);
        }

        return Ok(result);
    }

    [HttpDelete("{userId}")]
    public async Task<IActionResult> Delete(string userId)
    {
        var result = await _financialProfileService.DeleteAsync(userId);

        if (!result.Success)
        {
            return NotFound(result);
        }

        return Ok(result);
    }

    [HttpPost("{userId}/calculate-iq")]
    public async Task<IActionResult> CalculateIq(string userId)
    {
        var result = await _financialProfileService.CalculateIqAsync(userId);

        if (!result.Success)
            return BadRequest(result);

        return Ok(result);
    }
}