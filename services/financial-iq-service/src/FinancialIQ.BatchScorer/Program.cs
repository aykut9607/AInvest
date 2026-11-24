// Scores synthetic profiles with the production Financial IQ rules, offline.
//
//   dotnet run --project services/financial-iq-service/src/FinancialIQ.BatchScorer -- <input.json> <output.json>
//
// input:  JSON array of CalculateRequest objects (camelCase); unknown fields are ignored
// output: JSON array of { userId, score, segment, factorBreakdown } where factorBreakdown is the same object
//         the service returns (contracts/schemas/factor-breakdown.v2.schema.json)
using System.Text.Json;
using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;

if (args.Length != 2)
{
    Console.Error.WriteLine("usage: FinancialIQ.BatchScorer <input.json> <output.json>");
    return 1;
}

var json = new JsonSerializerOptions(JsonSerializerDefaults.Web) { WriteIndented = true };
var requests = JsonSerializer.Deserialize<List<CalculateRequest>>(File.ReadAllText(args[0]), json)
               ?? throw new InvalidDataException("input is not a JSON array of profiles");

var results = new List<object>(requests.Count);
foreach (var request in requests)
{
    // CalculateScore divides by the income; the service rejects income <= 0 before scoring, so do the same here
    if (request.MonthlyIncome <= 0)
    {
        Console.Error.WriteLine($"skipped {request.UserId}: monthly income must be greater than zero");
        continue;
    }

    var (score, segment, breakdown) = FinancialIqCommandManager.CalculateScore(request);
    results.Add(new
    {
        request.UserId,
        Score = score,
        Segment = segment,
        FactorBreakdown = JsonDocument.Parse(breakdown).RootElement,
    });
}

File.WriteAllText(args[1], JsonSerializer.Serialize(results, json));
Console.WriteLine($"scored {results.Count} of {requests.Count} profiles -> {args[1]}");
return 0;
