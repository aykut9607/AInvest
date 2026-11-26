import { describe, expect, it } from "vitest";
import { formatMoney, formatPercent, formatSigned, groupDigits, toDigits, wholeAmountDigits } from "./format";
import { factorRows, fallbackReasonLabel, portfolioReasonLabel, ruleSetsScore, warningLabel } from "./labels";
import { translateServerMessage } from "./messages";

describe("factorRows", () => {
  it("lists the v2 factors in a fixed order with Turkish labels and v2 maximums", () => {
    const rows = factorRows({
      version: "v2",
      factors: { Impatience: 8, SavingsRate: 15, CashReserveMonths: 15, ExpenseRatio: 9, DebtToIncomeRatio: 15 },
      warnings: [],
    });
    expect(rows.map((r) => [r.key, r.label, r.points, r.max])).toEqual([
      ["CashReserveMonths", "Nakit rezervi", 15, 25],
      ["DebtToIncomeRatio", "Borç/gelir oranı", 15, 25],
      ["SavingsRate", "Tasarruf oranı", 15, 25],
      ["ExpenseRatio", "Gider/gelir oranı", 9, 15],
      ["Impatience", "Sabır", 8, 10],
    ]);
  });

  it("uses factorMaximums when a later version sends it and shows unknown keys raw", () => {
    const rows = factorRows({
      version: "v3",
      factors: { CashReserveMonths: 20, SpendingStability: 7, Mystery: 1 },
      factorMaximums: { CashReserveMonths: 30, SpendingStability: 10 },
      warnings: [],
    });
    expect(rows).toEqual([
      { key: "CashReserveMonths", label: "Nakit rezervi", points: 20, max: 30 },
      { key: "SpendingStability", label: "SpendingStability", points: 7, max: 10 },
      { key: "Mystery", label: "Mystery", points: 1, max: null },
    ]);
  });

  it("shows a real v3 (v3c-i5) breakdown with its own keys, maximums and labels", () => {
    const rows = factorRows({
      version: "v3",
      factors: { CashReserveMonths: 30, InstallmentToIncome: 25, NetDebtToIncome: 10, SavingsRate: 19, Impatience: 0 },
      factorMaximums: { CashReserveMonths: 30, InstallmentToIncome: 25, NetDebtToIncome: 10, SavingsRate: 30, Impatience: 5 },
      warnings: ["High impatience"],
      appliedRule: "WEALTH_RUNWAY",
    });
    expect(rows.map((r) => [r.key, r.label, r.points, r.max])).toEqual([
      ["CashReserveMonths", "Nakit rezervi", 30, 30],
      ["InstallmentToIncome", "Taksit/gelir oranı", 25, 25],
      ["NetDebtToIncome", "Net borç/gelir oranı", 10, 10],
      ["SavingsRate", "Tasarruf oranı", 19, 30],
      ["Impatience", "Sabır", 0, 5],
    ]);
    expect(warningLabel("Installment without debt")).toBe("Borç yokken taksit bildirilmiş");
    expect(ruleSetsScore("WEALTH_RUNWAY")).toBe(false);
    expect(ruleSetsScore("SOLVENCY_CAP")).toBe(false);
    expect(ruleSetsScore("VERY_HIGH_INCOME")).toBe(true);
  });

  it("does not apply the v2 maximums to another version without factorMaximums", () => {
    expect(factorRows({ version: "v3", factors: { CashReserveMonths: 20 }, warnings: [] })[0].max).toBeNull();
    expect(factorRows(null)).toEqual([]);
  });
});

describe("labels", () => {
  it("translates warnings, fallback reasons and portfolio reasons", () => {
    expect(warningLabel("Low cash reserve")).toBe("Nakit rezervi düşük");
    expect(warningLabel("Something new")).toBe("Something new");
    expect(fallbackReasonLabel("UNVERIFIED_NUMBERS")).toBe("Model veride olmayan sayı yazdı");
    expect(fallbackReasonLabel(null)).toBe("");
    expect(portfolioReasonLabel("EXCLUDED_ASSET_REPLACED:BTC->GOLD")).toBe("İstemediğin Bitcoin yerine Altın kondu.");
    expect(portfolioReasonLabel("RESERVE_FIRST")).toContain("Acil durum fonun");
    expect(portfolioReasonLabel("<script>")).toBeNull();
  });

  it("translates known server messages and leaves unknown ones as they are", () => {
    expect(translateServerMessage("Financial profile not found.")).toBe("Kayıtlı finansal profil bulunamadı.");
    expect(translateServerMessage("Something else happened")).toBe("Something else happened");
  });
});

describe("format", () => {
  it("formats tr-TR money, percent and signed numbers", () => {
    expect(formatMoney(12500.4)).toBe("12.500 TL");
    expect(formatMoney(999999999999999)).toBe("999.999.999.999.999 TL");
    expect(formatPercent(18)).toBe("%18");
    expect(formatPercent(0.184, { ratio: true, fractionDigits: 1 })).toBe("%18,4");
    expect(formatSigned(5)).toBe("+5");
    expect(formatSigned(-3)).toBe("−3");
  });

  it("keeps amount inputs to at most 15 digits", () => {
    expect(toDigits("30.000")).toBe("30000");
    expect(toDigits("30,000 TL")).toBe("30000");
    expect(toDigits("0007")).toBe("7");
    expect(toDigits("1234567890123456789")).toBe("123456789012345");
    expect(groupDigits("999999999999999")).toBe("999.999.999.999.999");
    expect(groupDigits("")).toBe("");
    expect(wholeAmountDigits(1250.5)).toBe("1251");
    expect(wholeAmountDigits(0)).toBe("");
  });
});
