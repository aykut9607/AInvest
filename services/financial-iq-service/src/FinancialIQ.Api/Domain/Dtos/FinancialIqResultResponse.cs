using System.Text.Json;
using FinancialIQ.Api.Domain.Common;

namespace FinancialIQ.Api.Domain.Dtos;

public class FinancialIqResultResponse : IDto
{
    public Guid Id { get; set; }
    public string UserId { get; set; } = string.Empty;
    public int Score { get; set; }
    public string Segment { get; set; } = string.Empty;
    // contract v2: a JSON object { version, factors, warnings, appliedRule } (v1 sent it as a JSON string)
    public JsonElement FactorBreakdown { get; set; }
    public DateTime CreatedAt { get; set; }
    public DateTime UpdatedAt { get; set; }
    // changes every time this user's result is written again (from the row's rowversion, see ResultVersion).
    // Something built on a result (a portfolio proposal) keeps this number; if /latest returns another one,
    // the result has been recalculated since and that thing is out of date. Optional, added 22 Nov 2026
    public long ResultVersion { get; set; }
}
