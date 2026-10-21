using FinanceProfile.Api.Application.Abstract;
using FinanceProfile.Api.Application.Constants;
using FinanceProfile.Api.Application.Results;
using FinanceProfile.Api.Controllers;
using FinanceProfile.Api.DTOs;
using Microsoft.AspNetCore.Http;
using Microsoft.AspNetCore.Mvc;
using IResult = FinanceProfile.Api.Application.Results.IResult;

namespace FinanceProfile.Tests;

// checks only the HTTP status mapping of calculate-iq; the service behind the controller is faked
public class ProfilesControllerTests
{
    [Fact]
    public async Task CalculateIq_MissingProfile_Returns404()
    {
        var controller = new ProfilesController(new FakeService(
            new ErrorDataResult<FinancialIqCalculateResponse>(Messages.FinancialProfileNotFound)));

        var response = await controller.CalculateIq("nobody");

        Assert.IsType<NotFoundObjectResult>(response);
    }

    [Theory]
    [InlineData(Messages.FinancialIqServiceUnavailable)]
    [InlineData(Messages.FinancialIqCalculationFailed)]
    public async Task CalculateIq_IqServiceFailure_Returns502(string message)
    {
        var controller = new ProfilesController(new FakeService(
            new ErrorDataResult<FinancialIqCalculateResponse>(message)));

        var response = await controller.CalculateIq("u1");

        var objectResult = Assert.IsType<ObjectResult>(response);
        Assert.Equal(StatusCodes.Status502BadGateway, objectResult.StatusCode);
    }

    [Fact]
    public async Task CalculateIq_Success_Returns200()
    {
        var controller = new ProfilesController(new FakeService(
            new SuccessDataResult<FinancialIqCalculateResponse>(new FinancialIqCalculateResponse { Score = 70, Segment = "MEDIUM" }, "ok")));

        var response = await controller.CalculateIq("u1");

        Assert.IsType<OkObjectResult>(response);
    }

    private sealed class FakeService(IDataResult<FinancialIqCalculateResponse> calculateResult) : IFinancialProfileService
    {
        public Task<IDataResult<FinancialIqCalculateResponse>> CalculateIqAsync(string userId) => Task.FromResult(calculateResult);

        public Task<IDataResult<List<FinancialProfileResponse>>> GetAllAsync() => throw new NotSupportedException();
        public Task<IDataResult<FinancialProfileResponse>> GetByUserIdAsync(string userId) => throw new NotSupportedException();
        public Task<IResult> UpsertAsync(string id, UpsertFinancialProfileRequest request) => throw new NotSupportedException();
        public Task<IResult> DeleteAsync(string id) => throw new NotSupportedException();
    }
}
