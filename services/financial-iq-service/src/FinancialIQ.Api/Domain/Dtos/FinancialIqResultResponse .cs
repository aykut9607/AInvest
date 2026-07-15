using FinancialIQ.Api.Core.Entities;

namespace FinancialIQ.Api.Domain.Dtos;

public class FinancialIqResultResponse : IDto
{
    public Guid Id { get; set; }
    public string UserId { get; set; } = string.Empty;
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
}