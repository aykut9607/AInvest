using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Infrastructure.Abstract;

namespace FinancialIQ.Tests;

// in-memory stand-in for the read side; the real queries (usp_GetLatestIqResult, fn_IqTrend) run in SQL Server
internal sealed class FakeReadDal : IFinancialIqReadDal
{
    public Dictionary<string, FinancialIqResultResponse> Latest { get; } = new();
    public List<IqTrendPointResponse> Points { get; } = new();
    public string? LastRequestedUserId { get; private set; }
    public int LastRequestedTake { get; private set; }

    public Task<FinancialIqResultResponse?> GetLatestAsync(string userId)
    {
        LastRequestedUserId = userId;
        return Task.FromResult(Latest.GetValueOrDefault(userId));
    }

    public Task<List<IqTrendPointResponse>> GetTrendAsync(string userId, int take)
    {
        LastRequestedUserId = userId;
        LastRequestedTake = take;
        return Task.FromResult(Points.ToList());
    }

    // what the "database" returns for a payoff schedule, and the rate it was asked with (null = never asked)
    public List<DebtPayoffMonth> Schedule { get; } = new();
    public decimal? LastRequestedRate { get; private set; }

    public List<ScoringRulesResponse> ScoringVersions { get; } = new();

    public Task<List<ScoringRulesResponse>> GetScoringRulesAsync() => Task.FromResult(ScoringVersions.ToList());

    public Task<List<DebtPayoffMonth>> GetDebtPayoffScheduleAsync(decimal totalDebt, decimal monthlyPayment, decimal monthlyRate, int maxMonths)
    {
        LastRequestedRate = monthlyRate;
        return Task.FromResult(Schedule.ToList());
    }
}
