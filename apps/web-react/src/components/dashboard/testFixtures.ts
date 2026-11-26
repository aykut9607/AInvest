// Sample service responses for the dashboard tests (not used by the app).
import type { DebtPayoff, DebtPayoffMonth, FactorBreakdown, IqResult, IqTrendPoint } from "../../types/api";

export const BREAKDOWN: FactorBreakdown = {
  version: "v2",
  factors: { CashReserveMonths: 25, DebtToIncomeRatio: 25, SavingsRate: 25, ExpenseRatio: 9, Impatience: 8 },
  warnings: [],
  appliedRule: null,
};

export const LATEST: IqResult = {
  id: "r-1",
  userId: "u-1",
  score: 92,
  segment: "HIGH",
  factorBreakdown: BREAKDOWN,
  createdAt: "2026-11-20T10:00:00Z",
  updatedAt: "2026-11-24T11:05:00Z",
  resultVersion: 4711,
};

// shaped like demo.trend@ainvest.local after the seed script: 8 -> 37 -> 62 -> 92
export const TREND: IqTrendPoint[] = [
  { calculatedAt: "2026-11-01T09:00:00Z", score: 8, segment: "LOW", scoreChange: null, movingAverage3: 8 },
  { calculatedAt: "2026-11-08T09:00:00Z", score: 37, segment: "LOW", scoreChange: 29, movingAverage3: 22.5 },
  { calculatedAt: "2026-11-15T09:00:00Z", score: 62, segment: "MEDIUM", scoreChange: 25, movingAverage3: 35.666666 },
  { calculatedAt: "2026-11-22T09:00:00Z", score: 92, segment: "HIGH", scoreChange: 30, movingAverage3: 63.666666 },
];

// the same amortisation as dbo.fn_DebtPayoffSchedule (interest rounded to kuruş, the last month pays the rest)
export function payoffFor(totalDebt: number, monthlyPayment: number, monthlyInterestRate: number): DebtPayoff {
  const schedule: DebtPayoffMonth[] = [];
  let balance = totalDebt;
  while (balance > 0 && schedule.length < 600) {
    const interest = Math.round(balance * monthlyInterestRate * 100) / 100;
    const payment = Math.min(monthlyPayment, Math.round((balance + interest) * 100) / 100);
    const principal = Math.round((payment - interest) * 100) / 100;
    const closingBalance = Math.max(0, Math.round((balance - principal) * 100) / 100);
    schedule.push({ month: schedule.length + 1, openingBalance: balance, interest, payment, principal, closingBalance });
    balance = closingBalance;
  }
  const paidOff = balance === 0;
  return {
    totalDebt,
    monthlyPayment,
    monthlyInterestRate,
    paidOff,
    months: paidOff ? schedule.length : null,
    totalInterest: schedule.reduce((sum, m) => sum + m.interest, 0),
    totalPaid: schedule.reduce((sum, m) => sum + m.payment, 0),
    schedule,
  };
}
