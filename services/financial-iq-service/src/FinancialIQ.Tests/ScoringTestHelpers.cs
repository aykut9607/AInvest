using System.Globalization;
using System.Reflection;
using System.Text.Json;
using FinancialIQ.Api.Application.Concrete;
using FinancialIQ.Api.Domain.Dtos;

namespace FinancialIQ.Tests;

// shared helpers of the scoring tests: build a profile, score it, read the breakdown back
internal static class Scoring
{
    public static CalculateRequest Profile(decimal income, decimal expenses, decimal payment = 0, decimal debt = 0,
        decimal cash = 0, decimal investments = 0, int impatience = 3) => new()
    {
        UserId = "test-user",
        MonthlyIncome = income,
        MonthlyExpenses = expenses,
        MonthlyDebtPayment = payment,
        TotalDebt = debt,
        CashReserve = cash,
        InvestmentAmount = investments,
        ImpatienceLevel = impatience
    };

    public static Result Score(CalculateRequest request)
    {
        var (score, segment, factorBreakdown) = FinancialIqCommandManager.CalculateScore(request);
        return new Result(score, segment, factorBreakdown, JsonDocument.Parse(factorBreakdown).RootElement.Clone());
    }

    // a copy with one input changed (the request is mutable, the sample profiles must not be)
    public static CalculateRequest With(CalculateRequest r, string field, decimal value)
    {
        var copy = Profile(r.MonthlyIncome, r.MonthlyExpenses, r.MonthlyDebtPayment, r.TotalDebt, r.CashReserve, r.InvestmentAmount, r.ImpatienceLevel);
        copy.UserId = r.UserId;
        switch (field)
        {
            case nameof(CalculateRequest.MonthlyIncome): copy.MonthlyIncome = value; break;
            case nameof(CalculateRequest.MonthlyExpenses): copy.MonthlyExpenses = value; break;
            case nameof(CalculateRequest.MonthlyDebtPayment): copy.MonthlyDebtPayment = value; break;
            case nameof(CalculateRequest.TotalDebt): copy.TotalDebt = value; break;
            case nameof(CalculateRequest.CashReserve): copy.CashReserve = value; break;
            case nameof(CalculateRequest.InvestmentAmount): copy.InvestmentAmount = value; break;
            case nameof(CalculateRequest.ImpatienceLevel): copy.ImpatienceLevel = (int)value; break;
            default: throw new ArgumentException($"unknown field {field}");
        }
        return copy;
    }

    public static decimal Get(CalculateRequest r, string field) => field switch
    {
        nameof(CalculateRequest.MonthlyIncome) => r.MonthlyIncome,
        nameof(CalculateRequest.MonthlyExpenses) => r.MonthlyExpenses,
        nameof(CalculateRequest.MonthlyDebtPayment) => r.MonthlyDebtPayment,
        nameof(CalculateRequest.TotalDebt) => r.TotalDebt,
        nameof(CalculateRequest.CashReserve) => r.CashReserve,
        nameof(CalculateRequest.InvestmentAmount) => r.InvestmentAmount,
        nameof(CalculateRequest.ImpatienceLevel) => r.ImpatienceLevel,
        _ => throw new ArgumentException($"unknown field {field}")
    };

    public static readonly string[] MoneyFields =
    [
        nameof(CalculateRequest.MonthlyIncome), nameof(CalculateRequest.MonthlyExpenses), nameof(CalculateRequest.MonthlyDebtPayment),
        nameof(CalculateRequest.TotalDebt), nameof(CalculateRequest.CashReserve), nameof(CalculateRequest.InvestmentAmount)
    ];

    public sealed record Result(int Score, string Segment, string Json, JsonElement Breakdown)
    {
        public string? AppliedRule => Breakdown.GetProperty("appliedRule").GetString();
        public string[] Warnings => Breakdown.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()!).ToArray();
        public int Factor(string name) => Breakdown.GetProperty("factors").GetProperty(name).GetInt32();

        // in the order they were written
        public List<KeyValuePair<string, int>> Factors => Pairs("factors");
        public List<KeyValuePair<string, int>> FactorMaximums => Pairs("factorMaximums");

        private List<KeyValuePair<string, int>> Pairs(string property) =>
            Breakdown.GetProperty(property).EnumerateObject().Select(p => KeyValuePair.Create(p.Name, p.Value.GetInt32())).ToList();
    }
}

// a deterministic sample of profiles for the property tests: the same profiles on every run (fixed seed), from tiny to
// very large incomes, with and without debt, investments and installments, including the solvency cap and the runway
internal static class SampleProfiles
{
    public static IReadOnlyList<CalculateRequest> All { get; } = Build(400, seed: 42).Concat(GoldenTable.Cases.Select(c => c.Request)).ToList();

    private static List<CalculateRequest> Build(int count, int seed)
    {
        var rng = new Random(seed);
        decimal Amount(decimal of, double maxTimes, double zeroChance) =>
            rng.NextDouble() < zeroChance ? 0m : Math.Round(of * (decimal)(rng.NextDouble() * maxTimes), 2);

        var profiles = new List<CalculateRequest>(count);
        for (var i = 0; i < count; i++)
        {
            // log-uniform monthly income between 100 and 5,000,000
            var income = Math.Round((decimal)Math.Exp(Math.Log(100) + rng.NextDouble() * (Math.Log(5_000_000) - Math.Log(100))), 2);
            var expenses = Amount(income, 1.6, 0.08);
            var payment = Amount(income, 0.7, 0.4);
            // up to 20 years of income: past the solvency cap (5 to 15 years) now and then
            var debt = Amount(income * 12, 20 * rng.NextDouble(), 0.35);
            var cash = Amount(income, 40, 0.2);
            // up to 300 months of income: enough for a wealth runway now and then
            var investments = Amount(income, 300 * rng.NextDouble(), 0.6);
            profiles.Add(Scoring.Profile(income, expenses, payment, debt, cash, investments, rng.Next(1, 6)));
            profiles[^1].UserId = $"sample-{i}";
        }
        return profiles;
    }
}

// the v3c-i5 column of the Python reference's golden table (TestData/iq_v3_golden.v3c-i5.json, embedded)
internal static class GoldenTable
{
    public sealed record Case(string Id, CalculateRequest Request, IReadOnlyDictionary<string, decimal> Intermediates,
        int Score, string Segment, List<KeyValuePair<string, int>> Factors, string[] Warnings, string? AppliedRule);

    private static readonly Lazy<(List<KeyValuePair<string, int>> Maximums, List<Case> Cases)> Data = new(Load);

    public static List<KeyValuePair<string, int>> FactorMaximums => Data.Value.Maximums;
    public static IReadOnlyList<Case> Cases => Data.Value.Cases;
    public static Case Get(string id) => Cases.Single(c => c.Id == id);

    private static (List<KeyValuePair<string, int>>, List<Case>) Load()
    {
        using var stream = Assembly.GetExecutingAssembly().GetManifestResourceStream("iq_v3_golden.v3c-i5.json")
                           ?? throw new InvalidOperationException("embedded golden table missing");
        using var document = JsonDocument.Parse(stream);
        var root = document.RootElement;

        var maximums = Pairs(root.GetProperty("factorMaximums"));
        var cases = root.GetProperty("cases").EnumerateArray().Select(c =>
        {
            var input = c.GetProperty("input");
            var request = Scoring.Profile(
                input.GetProperty("monthlyIncome").GetDecimal(), input.GetProperty("monthlyExpenses").GetDecimal(),
                input.GetProperty("monthlyDebtPayment").GetDecimal(), input.GetProperty("totalDebt").GetDecimal(),
                input.GetProperty("cashReserve").GetDecimal(), input.GetProperty("investmentAmount").GetDecimal(),
                input.GetProperty("impatienceLevel").GetInt32());
            var id = c.GetProperty("id").GetString()!;
            request.UserId = id;

            var intermediates = c.GetProperty("intermediates").EnumerateObject()
                .ToDictionary(p => p.Name, p => decimal.Parse(p.Value.GetString()!, NumberStyles.Float, CultureInfo.InvariantCulture));

            var expected = c.GetProperty("expected");
            return new Case(id, request, intermediates,
                expected.GetProperty("score").GetInt32(),
                expected.GetProperty("segment").GetString()!,
                Pairs(expected.GetProperty("factors")),
                expected.GetProperty("warnings").EnumerateArray().Select(w => w.GetString()!).ToArray(),
                expected.GetProperty("appliedRule").GetString());
        }).ToList();

        return (maximums, cases);
    }

    private static List<KeyValuePair<string, int>> Pairs(JsonElement element) =>
        element.EnumerateObject().Select(p => KeyValuePair.Create(p.Name, p.Value.GetInt32())).ToList();
}
