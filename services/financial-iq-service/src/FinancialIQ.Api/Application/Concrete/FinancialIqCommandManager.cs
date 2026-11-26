using FinancialIQ.Api.Application.Abstract;
using FinancialIQ.Api.Application.Constants;
using FinancialIQ.Api.Application.Results;
using FinancialIQ.Api.Domain.Entities;
using FinancialIQ.Api.Domain.Dtos;
using FinancialIQ.Api.Infrastructure.Abstract;
using System.Text.Json;

namespace FinancialIQ.Api.Application.Concrete;

// CQRS-lite write side: validation, the scoring rules and saving. The reads are in FinancialIqQueryManager.
public class FinancialIqCommandManager : IFinancialIqCommandService
{
    private readonly IFinancialIqResultDal _dal;

    // the most each factor can give (sum = 100), in display order; also sent in factorBreakdown.factorMaximums so the
    // apps can draw the bars of any version without their own table. v3: 30 / 25 / 10 / 30 / 5
    internal static readonly IReadOnlyDictionary<string, int> FactorMaximums =
        ScoringRules.Factors.ToDictionary(f => f.Name, f => f.MaxPoints);

    public FinancialIqCommandManager(IFinancialIqResultDal dal)
    {
        _dal = dal;
    }

    public async Task<IDataResult<FinancialIqResultResponse>> CalculateAsync(CalculateRequest request)
    {
        // without a user id the result could not be found again (and empty ids would all share one row)
        if (string.IsNullOrWhiteSpace(request.UserId) || request.UserId.Length > FinancialIqResult.UserIdMaxLength)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidUserId);

        if (request.MonthlyIncome <= 0)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidMonthlyIncome);

        if (request.MonthlyExpenses < 0 || request.MonthlyDebtPayment < 0 || request.CashReserve < 0 || request.TotalDebt < 0 || request.InvestmentAmount < 0)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.NegativeAmountNotAllowed);

        if (request.ImpatienceLevel < 1 || request.ImpatienceLevel > 5)
            return new ErrorDataResult<FinancialIqResultResponse>(Messages.InvalidImpatienceLevel);

        var (score, segment, factorBreakdown) = CalculateScore(request);


        var entity = new FinancialIqResult
        {
            UserId = request.UserId,
            Score = score,
            Segment = segment,
            FactorBreakdown = factorBreakdown,
            ScoringVersion = ScoringRules.ScoringVersion,
            UpdatedAt = DateTime.UtcNow
        };

        await _dal.SaveAsync(entity);

        var saved = await _dal.GetAsync(x => x.UserId == request.UserId);
        return new SuccessDataResult<FinancialIqResultResponse>(MapToResponse(saved!), Messages.FinancialIqResultCalculated);
    }

    // --- Core scoring logic (scoring v3, evaluation/IQ_V3_PROPOSAL.md section 8) ---
    // returns the breakdown as JSON text because that is how it is stored (nvarchar(max)); the API turns it into an object.
    // All arithmetic is decimal and in the order of the Python reference (evaluation/iq_v3/scoring.py); the golden
    // table test (GoldenTableTests) checks every measure, factor, warning and label against it
    internal static (int score, string segment, string factorBreakdown) CalculateScore(CalculateRequest r)
    {
        // 1) the measures (liquid assets, outflow, net debt, ...), see Measure below
        var m = Measure(r);

        // 2) each factor's share (0..1) of its maximum; the wealth runway is a floor for the cash-flow factors
        var scored = Shares(r, m, m.RunwayShare);

        // 3) points = maximum * share * solvency cap, rounded per factor; the score is their sum, so the bars in the
        //    apps always add up to the score
        //example lets say the reserve share is 0.05 (0.25 months) and the cap 1: 30 * 0.05 * 1 = 1.5 -> 2 points
        var factorScores = Points(scored, m.SolvencyCap);
        var totalScore = factorScores.Values.Sum();

        var warnings = Warnings(r, m, scored);
        var appliedRule = AppliedRule(r, m, totalScore);

        var segment = totalScore switch
        {
            >= ScoringRules.HighSegmentMinScore => "HIGH",
            >= ScoringRules.MediumSegmentMinScore => "MEDIUM",
            _ => "LOW"
        };
        // bundle scores + warnings into one JSON document so the AI/RAG service can explain "why" this score, not just "what".
        // appliedRule is only a label (SOLVENCY_CAP, WEALTH_RUNWAY or null); version tells results of older rules apart
        var breakdown = new { version = ScoringRules.ScoringVersion, factors = factorScores, factorMaximums = FactorMaximums, warnings, appliedRule };
        var factorBreakdownJson = JsonSerializer.Serialize(breakdown);
        return (totalScore, segment, factorBreakdownJson);
    }

    // the measures of one profile, in the order they are calculated (internal: the tests compare them with the golden table)
    internal sealed record Measures(
        decimal LiquidAssets, decimal EffectiveExpenses, decimal ReserveExpenses, decimal MonthlyOutflow, decimal ReserveMonths,
        decimal ExcessLiquidAssets, decimal NetDebt, decimal NetDebtYears, decimal EffectiveDebtPayment,
        decimal InstallmentRatio, decimal SavingsRate, decimal LiquidNetWorth, decimal RunwayYears,
        decimal RunwayShare, decimal SolvencyCap);

    // every example below is the sample weak profile (CLAUDE.md 6.7): income 30,000, expenses 25,000, installment 7,000,
    // total debt 90,000, cash 3,000, investments 10,000
    internal static Measures Measure(CalculateRequest r)
    {
        // liquid assets: the cash plus half of the investments, used for the reserve, the debt offset and the runway
        var liquidAssets = r.CashReserve + r.InvestmentAmount * ScoringRules.InvestmentLiquidShare;
        //example lets say cash is 3000 and investments are 10000, then liquidAssets = 3000 + 10000 * 0.5 = 8000

        // expenses below 10% of the income count as 10%, only in the savings rate (they are flagged as too low)
        var effectiveExpenses = Math.Max(r.MonthlyExpenses, r.MonthlyIncome * ScoringRules.ExpenseFloorShare);
        //example lets say expenses are 25000 and income is 30000, then effectiveExpenses = max(25000, 3000) = 25000

        // the reserve and the runway are measured in expenses of at least 2,000 TL; NOT the 10% income floor: that one
        // grows with the income, so more income would mean fewer reserve months and a lower score
        var reserveExpenses = Math.Max(r.MonthlyExpenses, ScoringRules.ExpenseFloorTl);
        //example max(25000, 2000) = 25000

        // what leaves the account every month: the installment has to be paid from the reserve too
        var monthlyOutflow = reserveExpenses + r.MonthlyDebtPayment;
        //example 25000 + 7000 = 32000

        // months the liquid assets cover the outflow; never a division by zero, the outflow is at least 2,000 TL
        var reserveMonths = liquidAssets / monthlyOutflow;
        //example 8000 / 32000 = 0.25 months

        // liquid assets first fill the emergency target (6 months of outflow); only what is above it offsets the debt,
        // so the same lira is not counted in the reserve and against the debt
        var excessLiquidAssets = Math.Max(0m, liquidAssets - monthlyOutflow * ScoringRules.ReserveTargetMonths);
        //example max(0, 8000 - 32000 * 6) = 0
        var netDebt = Math.Max(0m, r.TotalDebt - excessLiquidAssets);
        //example max(0, 90000 - 0) = 90000

        // the net debt in years of gross income
        var netDebtYears = netDebt / (r.MonthlyIncome * 12);
        //example 90000 / (30000 * 12) = 0.25 years

        // the debt service is at least the monthly interest of the net debt; a smaller installment means a growing debt
        var effectiveDebtPayment = Math.Max(r.MonthlyDebtPayment, netDebt * ScoringRules.InterestFloorMonthlyRate);
        //example max(7000, 90000 * 0.035 = 3150) = 7000

        var installmentRatio = effectiveDebtPayment / r.MonthlyIncome;
        //example 7000 / 30000 = 0.2333 -> 23% of the income goes to debt

        var savingsRate = (r.MonthlyIncome - effectiveExpenses - effectiveDebtPayment) / r.MonthlyIncome;
        //example (30000 - 25000 - 7000) / 30000 = -0.0667 -> spends 6.7% more than earns

        // wealth runway: years of expenses the liquid net worth would pay for (0 when the debt is larger)
        var liquidNetWorth = liquidAssets - r.TotalDebt;
        var runwayYears = liquidNetWorth > 0 ? liquidNetWorth / (reserveExpenses * 12) : 0m;
        //example 8000 - 90000 = -82000 -> no runway (0 years)
        //example lets say liquid assets are 6,500,000, debt 1,000,000 and expenses 29,000 -> 5,500,000 / 348,000 = 15.8 years

        return new Measures(liquidAssets, effectiveExpenses, reserveExpenses, monthlyOutflow, reserveMonths, excessLiquidAssets, netDebt,
            netDebtYears, effectiveDebtPayment, installmentRatio, savingsRate, liquidNetWorth, runwayYears,
            // runway share: 15.8 / 25 = 0.63 (25 years = the 4% rule); solvency cap: 1 up to 5 years of net debt, 0 from 15
            RunwayShare: ScoringRules.WealthRunway.Share(runwayYears),
            SolvencyCap: ScoringRules.SolvencyCap.Share(netDebtYears));
    }

    // one factor of one profile: the value it is scored on and the share of its maximum it earned
    private sealed record ScoredFactor(ScoringFactor Factor, decimal Measure, decimal Share);

    // runwayShare lifts the factors with LiftedByWealthRunway (the cash-flow ones); AppliedRule calls it again with 0
    private static List<ScoredFactor> Shares(CalculateRequest r, Measures m, decimal runwayShare)
    {
        // the value each factor is scored on, in display order (ScoringRules.Factors)
        (ScoringFactor factor, decimal measure)[] factors =
        [
            (ScoringRules.CashReserveMonths, m.ReserveMonths),
            (ScoringRules.InstallmentToIncome, m.InstallmentRatio),
            (ScoringRules.NetDebtToIncome, m.NetDebtYears),
            (ScoringRules.SavingsRate, m.SavingsRate),
            (ScoringRules.Impatience, r.ImpatienceLevel)
        ];
        //example the sample profile: reserve 0.25 months -> 0.05, installment 23% -> 0.517, net debt 0.25 years -> 1,
        // savings -6.7% -> 0.067, impatience 5 -> 0

        return factors.Select(f =>
        {
            var share = f.factor.Scale.Share(f.measure);
            //example lets say the runway share is 0.63 and the savings rate -3% (share 0.14) -> the savings share is 0.63
            if (f.factor.LiftedByWealthRunway) share = Math.Max(share, runwayShare);
            return new ScoredFactor(f.factor, f.measure, share);
        }).ToList();
    }

    // factor name -> points, in display order; cap = 1 gives the points before the solvency cap (used for the warnings)
    private static Dictionary<string, int> Points(List<ScoredFactor> scored, decimal solvencyCap) =>
        scored.ToDictionary(f => f.Factor.Name, f => RoundPoints(f.Factor.MaxPoints * f.Share * solvencyCap));

    // half up, in two steps: 6 decimals first, then an integer. Not banker's rounding (C#'s default), which turns
    // 12.5 into 12; every value here is >= 0, so AwayFromZero is half up
    //example 1.5 -> 2, 12.5 -> 13, 2.4999999999999999999999999995 (division noise of a 2.5) -> 2.500000 -> 3
    internal static int RoundPoints(decimal value) =>
        (int)Math.Round(Math.Round(value, ScoringRules.PointsPreRoundingDecimals, MidpointRounding.AwayFromZero), 0, MidpointRounding.AwayFromZero);

    // fixed order, no duplicates: factor warnings (factor order), the cap, then consistency and data quality
    private static List<string> Warnings(CalculateRequest r, Measures m, List<ScoredFactor> scored)
    {
        var warnings = new List<string>();

        // a factor below 60% of its maximum always has its warning (from the points before the cap: the cap has its own)
        //example lets say the installment factor gets 13 of 25 (< 15) and the installment is 23% of the income
        // (not above 36%) -> "Elevated debt burden"
        foreach (var f in scored)
        {
            if (RoundPoints(f.Factor.MaxPoints * f.Share) < f.Factor.MaxPoints * ScoringRules.WarningShare)
                warnings.Add(f.Factor.Warning.TextFor(f.Measure));
        }

        // the solvency cap took points away (net debt above 5 years of income)
        if (m.SolvencyCap < 1) warnings.Add(ScoringRules.ExtremeDebtWarning);

        // the installment does not even pay the interest of the net debt
        //example lets say the net debt is 2,000,000 and the installment 2,000 < 70,000 -> the debt grows every month
        if (m.NetDebt > 0 && r.MonthlyDebtPayment < m.NetDebt * ScoringRules.InterestFloorMonthlyRate)
            warnings.Add(ScoringRules.InstallmentBelowInterestWarning);

        // data quality: flagged, never rejected
        if (r.MonthlyExpenses < r.MonthlyIncome * ScoringRules.ExpenseFloorShare) warnings.Add(ScoringRules.ExpensesTooLowWarning);
        if (r.MonthlyDebtPayment > 0 && r.TotalDebt == 0) warnings.Add(ScoringRules.InstallmentWithoutDebtWarning);
        if (r.TotalDebt > 0 && r.MonthlyDebtPayment > r.TotalDebt) warnings.Add(ScoringRules.InstallmentExceedsDebtWarning);

        return warnings;
    }

    // a label that explains the score; it never sets it (the score is always the sum of the factor points)
    //  SOLVENCY_CAP:  the cap is below 1 (net debt above 5 years of income)
    //  WEALTH_RUNWAY: a runway of at least 5 years (ScoringRules.WealthRunwayLabelMinYears) lifted a factor enough to
    //                 raise the score (the same calculation without it scores lower)
    private static string? AppliedRule(CalculateRequest r, Measures m, int score)
    {
        if (m.SolvencyCap < 1) return ScoringRules.SolvencyCapRule;

        //example lets say the runway is 15.8 years (share 0.63) and the savings rate 3%: savings 19 points with it,
        // 10 without it, score 84 instead of 75 -> WEALTH_RUNWAY
        //example lets say the runway is 0.42 years: it lifts the score from 25 to 26, but that is no wealth -> null
        if (m.RunwayYears >= ScoringRules.WealthRunwayLabelMinYears &&
            score > Points(Shares(r, m, runwayShare: 0m), m.SolvencyCap).Values.Sum())
            return ScoringRules.WealthRunwayRule;

        return null;
    }

    internal static FinancialIqResultResponse MapToResponse(FinancialIqResult entity) => new()
    {
        Id = entity.Id,
        UserId = entity.UserId,
        Score = entity.Score,
        Segment = entity.Segment,
        FactorBreakdown = FactorBreakdownJson.ToElement(entity.FactorBreakdown),
        CreatedAt = entity.CreatedAt,
        UpdatedAt = entity.UpdatedAt,
        ResultVersion = ResultVersion.FromRowVersion(entity.RowVersion)
    };
}
