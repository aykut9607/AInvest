import { describe, expect, it } from "vitest";
import type { Alert, DebtPayoff } from "../../types/api";
import { BREAKDOWN, LATEST, TREND } from "./testFixtures";
import {
  balanceSeries,
  currentResult,
  debtState,
  describeTrendPoint,
  factorRatio,
  factorTone,
  formatMonths,
  freshCalculation,
  parsePercentInput,
  percentToRate,
  percentToText,
  sortAlerts,
  trendAxisLabels,
  trendRows,
  trendSummary,
} from "./dashboardData";

describe("freshCalculation", () => {
  it("accepts the calculation the profile page passes", () => {
    const fresh = freshCalculation({ calculation: { score: 92, segment: "HIGH", factorBreakdown: BREAKDOWN } });
    expect(fresh).toEqual({ score: 92, segment: "HIGH", factorBreakdown: BREAKDOWN });
  });

  it("ignores anything else in location.state", () => {
    expect(freshCalculation(null)).toBeUndefined();
    expect(freshCalculation({ from: "/asistan" })).toBeUndefined();
    expect(freshCalculation({ calculation: { score: "92", segment: "HIGH" } })).toBeUndefined();
    expect(freshCalculation({ calculation: { score: 92, segment: "VERY_HIGH" } })).toBeUndefined();
  });

  it("keeps a missing breakdown as null", () => {
    expect(freshCalculation({ calculation: { score: 50, segment: "MEDIUM" } })?.factorBreakdown).toBeNull();
  });
});

describe("currentResult", () => {
  const fresh = { score: 62, segment: "MEDIUM" as const, factorBreakdown: null };

  it("prefers the loaded /latest result, with its time", () => {
    const result = currentResult(fresh, LATEST);
    expect(result?.score).toBe(92);
    expect(result?.calculatedAt).toBe("2026-11-24T11:05:00Z");
    // sent to the Coach exactly as received
    expect(result?.factorBreakdown).toBe(BREAKDOWN);
  });

  it("shows the fresh calculation until /latest is there (or when it failed / was empty)", () => {
    expect(currentResult(fresh, undefined)).toMatchObject({ score: 62, segment: "MEDIUM", calculatedAt: null });
    expect(currentResult(fresh, null)?.score).toBe(62);
  });

  it("returns null when there is nothing to show", () => {
    expect(currentResult(undefined, undefined)).toBeNull();
    expect(currentResult(undefined, null)).toBeNull();
  });

  it("gives the same key for the same content, a new one for a new result", () => {
    const fromFresh = currentResult({ score: 92, segment: "HIGH", factorBreakdown: BREAKDOWN }, undefined);
    expect(fromFresh?.key).toBe(currentResult(undefined, LATEST)?.key);
    expect(currentResult(fresh, undefined)?.key).not.toBe(fromFresh?.key);
  });
});

describe("factor tones", () => {
  it("uses the mobile thresholds: >= 70 % good, >= 40 % warning, else critical", () => {
    expect(factorTone(25, 25)).toBe("good");
    expect(factorTone(7, 10)).toBe("good");
    expect(factorTone(15, 25)).toBe("warning");
    expect(factorTone(4, 10)).toBe("warning");
    expect(factorTone(8, 25)).toBe("critical");
    expect(factorTone(0, 15)).toBe("critical");
  });

  it("clamps the ratio to 0..1", () => {
    expect(factorRatio(30, 25)).toBe(1);
    expect(factorRatio(-1, 25)).toBe(0);
    expect(factorRatio(5, 0)).toBe(0);
  });
});

describe("sortAlerts", () => {
  it("orders CRITICAL -> WARNING -> INFO and keeps the order within a level", () => {
    const alerts: Alert[] = [
      { code: "HIGH_IMPATIENCE", severity: "INFO", message: "i" },
      { code: "LOW_RESERVE", severity: "WARNING", message: "w1" },
      { code: "MONTHLY_DEFICIT", severity: "CRITICAL", message: "c" },
      { code: "HIGH_INSTALLMENT", severity: "WARNING", message: "w2" },
    ];
    expect(sortAlerts(alerts).map((a) => a.message)).toEqual(["c", "w1", "w2", "i"]);
    // the input is not changed
    expect(alerts[0].message).toBe("i");
  });

  it("puts an unknown severity last", () => {
    const alerts = [
      { code: "X", severity: "NEW_LEVEL", message: "x" },
      { code: "I", severity: "INFO", message: "i" },
    ] as unknown as Alert[];
    expect(sortAlerts(alerts).map((a) => a.code)).toEqual(["I", "X"]);
  });
});

describe("trend helpers", () => {
  it("builds table rows with a signed change, a dash for the first one and one decimal averages", () => {
    const rows = trendRows(TREND);
    expect(rows.map((r) => r.change)).toEqual(["–", "+29", "+25", "+30"]);
    expect(rows.map((r) => r.average)).toEqual(["8", "22,5", "35,7", "63,7"]);
    // Istanbul time (UTC+3)
    expect(rows[3].date).toBe("22.11.2026 12:00");
    expect(trendRows([{ ...TREND[1], scoreChange: -3 }])[0].change).toBe("−3");
  });

  it("summarises the history for screen readers", () => {
    expect(trendSummary(TREND)).toBe(
      "Skor geçmişi grafiği, 4 hesaplama: ilk skor 8, son skor 92, en düşük 8, en yüksek 92."
    );
    expect(trendSummary([])).toBe("Skor geçmişi yok.");
    expect(describeTrendPoint(TREND[0])).toContain("skor 8, değişim –, 3'lü ortalama 8");
  });

  it("labels the x axis with dates, or with times when every calculation is on the same day", () => {
    expect(trendAxisLabels(TREND)).toEqual(["01.11.2026", "08.11.2026", "15.11.2026", "22.11.2026"]);
    const sameDay = TREND.map((p, i) => ({ ...p, calculatedAt: `2026-11-24T1${i}:05:00Z` }));
    // Istanbul is UTC+3
    expect(trendAxisLabels(sameDay)).toEqual(["13:05", "14:05", "15:05", "16:05"]);
  });
});

describe("interest input", () => {
  it("accepts percent with a comma or a dot, 0 included", () => {
    expect(parsePercentInput("3,5")).toEqual({ ok: true, value: 3.5 });
    expect(parsePercentInput(" 3.5 ")).toEqual({ ok: true, value: 3.5 });
    expect(parsePercentInput("0")).toEqual({ ok: true, value: 0 });
    expect(parsePercentInput("%4,25")).toEqual({ ok: true, value: 4.25 });
    expect(parsePercentInput("100")).toEqual({ ok: true, value: 100 });
  });

  it("rejects text, negatives and values over 100", () => {
    for (const text of ["", "abc", "-1", "101", "3,5,1", "1e2"]) {
      expect(parsePercentInput(text).ok).toBe(false);
    }
  });

  it("converts percent to the service's rate without floating noise and back to text", () => {
    expect(percentToRate(3.5)).toBe(0.035);
    expect(percentToRate(2.7)).toBe(0.027);
    expect(String(percentToRate(2.7))).toBe("0.027");
    expect(percentToRate(0)).toBe(0);
    expect(percentToText(3.5)).toBe("3,5");
  });
});

describe("debt helpers", () => {
  it("writes months with years from 12 on", () => {
    expect(formatMonths(7)).toBe("7 ay");
    expect(formatMonths(12)).toBe("12 ay (1 yıl)");
    expect(formatMonths(13)).toBe("13 ay (1 yıl 1 ay)");
    expect(formatMonths(600)).toBe("600 ay (50 yıl)");
  });

  const base: DebtPayoff = {
    totalDebt: 6000,
    monthlyPayment: 3000,
    monthlyInterestRate: 0,
    paidOff: true,
    months: 2,
    totalInterest: 0,
    totalPaid: 6000,
    schedule: [
      { month: 1, openingBalance: 6000, interest: 0, payment: 3000, principal: 3000, closingBalance: 3000 },
      { month: 2, openingBalance: 3000, interest: 0, payment: 3000, principal: 3000, closingBalance: 0 },
    ],
  };

  it("starts the balance series with today's debt", () => {
    expect(balanceSeries(base).map((p) => [p.month, p.balance])).toEqual([
      [0, 6000],
      [1, 3000],
      [2, 0],
    ]);
    expect(balanceSeries({ ...base, schedule: [] })).toEqual([]);
  });

  it("tells no debt, paid off and not paid off apart", () => {
    expect(debtState(base)).toBe("paid-off");
    expect(debtState({ ...base, totalDebt: 0, months: 0, schedule: [] })).toBe("no-debt");
    expect(debtState({ ...base, paidOff: false, months: null, schedule: [] })).toBe("not-paid-off");
  });
});
