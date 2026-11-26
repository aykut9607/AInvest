import { describe, expect, it } from "vitest";
import { SAMPLE_PORTFOLIO_PROPOSAL } from "../../mocks/portfolioProposal";
import { MemoryStorage } from "../../test/helpers";
import type { IqResult } from "../../types/api";
import { EMPTY_PREFERENCES, loadPreferences, missingChoices, parsePreferences, savePreferences, toggleAsset } from "./preferences";
import { allocationParts, disclaimerText, isProposalStale, labelFits, reasonText, swatchFor } from "./proposal";
import { ceilingNote, clampRisk, isRiskAllowed, maxRiskForSegment } from "./risk";

class ThrowingStorage extends MemoryStorage {
  override getItem(): string | null {
    throw new Error("blocked");
  }
  override setItem(): void {
    throw new Error("quota");
  }
}

describe("risk ceiling", () => {
  it("allows levels up to the IQ segment and locks the ones above", () => {
    expect(maxRiskForSegment("LOW")).toBe("LOW");
    expect(maxRiskForSegment("MEDIUM")).toBe("MEDIUM");
    expect(maxRiskForSegment("HIGH")).toBe("HIGH");
    expect(maxRiskForSegment(null)).toBe("LOW");

    expect(isRiskAllowed("LOW", "LOW")).toBe(true);
    expect(isRiskAllowed("MEDIUM", "LOW")).toBe(false);
    expect(isRiskAllowed("MEDIUM", "MEDIUM")).toBe(true);
    expect(isRiskAllowed("HIGH", "MEDIUM")).toBe(false);
    expect(isRiskAllowed("HIGH", "HIGH")).toBe(true);
  });

  it("shows a stored choice above today's ceiling as the ceiling and keeps 'not chosen'", () => {
    expect(clampRisk("HIGH", "MEDIUM")).toBe("MEDIUM");
    expect(clampRisk("LOW", "HIGH")).toBe("LOW");
    expect(clampRisk(null, "HIGH")).toBeNull();
  });

  it("words the ceiling neutrally", () => {
    expect(ceilingNote("MEDIUM")).toBe("IQ segmentin şu an en fazla orta seviyesine izin veriyor; skorun yükseldikçe açılır.");
    expect(ceilingNote("LOW")).toContain("en fazla düşük");
    expect(ceilingNote("HIGH")).toContain("hepsine izin veriyor");
    for (const level of ["LOW", "MEDIUM", "HIGH"] as const) expect(ceilingNote(level)).not.toMatch(/diyorsun/);
  });
});

describe("portfolio preferences", () => {
  it("drops unknown values when restoring and reports what is missing", () => {
    expect(parsePreferences(null)).toEqual(EMPTY_PREFERENCES);
    const parsed = parsePreferences({
      option: "CUSTOM",
      riskLevel: "EXTREME",
      institutionStyle: "BANK",
      focusAssets: ["GOLD", "GOLD", "UNKNOWN", 7],
      excludedAssets: ["BTC", "NOPE"],
    });
    expect(parsed).toEqual({ option: "CUSTOM", riskLevel: null, institutionStyle: null, focusAssets: ["GOLD"], excludedAssets: ["BTC"] });
    expect(missingChoices(parsed)).toEqual(["risk seviyesi"]);
    expect(missingChoices({ ...parsed, focusAssets: [] })).toEqual(["en az bir odak alanı", "risk seviyesi"]);
    expect(missingChoices(EMPTY_PREFERENCES)).toEqual(["portföy türü", "risk seviyesi"]);
    expect(missingChoices({ ...EMPTY_PREFERENCES, option: "INSTITUTION", riskLevel: "LOW" })).toEqual(["kurum tarzı"]);
  });

  it("round-trips through storage and survives storage that throws", () => {
    const storage = new MemoryStorage();
    const prefs = { ...EMPTY_PREFERENCES, option: "STANDARD" as const, riskLevel: "MEDIUM" as const, excludedAssets: ["BTC"] };
    expect(savePreferences(storage, "k", prefs)).toBe(true);
    expect(loadPreferences(storage, "k")).toEqual(prefs);

    const blocked = new ThrowingStorage();
    expect(savePreferences(blocked, "k", prefs)).toBe(false);
    expect(loadPreferences(blocked, "k")).toEqual(EMPTY_PREFERENCES);
    expect(loadPreferences(null, "k")).toEqual(EMPTY_PREFERENCES);
  });

  it("toggles assets", () => {
    expect(toggleAsset([], "GOLD")).toEqual(["GOLD"]);
    expect(toggleAsset(["GOLD", "BTC"], "GOLD")).toEqual(["BTC"]);
  });
});

describe("proposal helpers", () => {
  it("translates known reason codes and falls back to the raw code", () => {
    expect(reasonText("EXCLUDED_ASSET_REPLACED:BTC->GOLD")).toEqual({ text: "İstemediğin Bitcoin yerine Altın kondu.", raw: false });
    expect(reasonText("RISK_CAPPED_BY_IQ").raw).toBe(false);
    expect(reasonText("NEW_REASON_FROM_V2")).toEqual({ text: "NEW_REASON_FROM_V2", raw: true });
  });

  it("translates the English disclaimer and keeps other text", () => {
    expect(disclaimerText("This is not investment advice.")).toBe("Bu bir yatırım tavsiyesi değildir.");
    expect(disclaimerText("")).toBe("Bu bir yatırım tavsiyesi değildir.");
    expect(disclaimerText("Yatırım tavsiyesi değildir.")).toBe("Yatırım tavsiyesi değildir.");
  });

  const latest = (score: number, updatedAt: string): Pick<IqResult, "score" | "updatedAt" | "createdAt"> => ({
    score,
    updatedAt,
    createdAt: "2026-11-01T00:00:00Z",
  });

  it("flags a service proposal based on an older IQ, never the sample", () => {
    const proposal = SAMPLE_PORTFOLIO_PROPOSAL; // based on IQ 88 calculated 2026-11-26T09:58:00Z
    expect(isProposalStale(proposal, latest(88, "2026-11-26T09:58:00Z"), "service")).toBe(false);
    expect(isProposalStale(proposal, latest(88, "2026-11-27T08:00:00Z"), "service")).toBe(true);
    expect(isProposalStale(proposal, latest(62, "2026-11-25T08:00:00Z"), "service")).toBe(true);
    expect(isProposalStale(proposal, latest(62, "2026-11-27T08:00:00Z"), "mock")).toBe(false);
    expect(isProposalStale(proposal, null, "service")).toBe(false);
    expect(isProposalStale(proposal, latest(88, "not a date"), "service")).toBe(false);
  });

  it("gives the allocation parts categorical slots in the service's order", () => {
    const parts = allocationParts(SAMPLE_PORTFOLIO_PROPOSAL.allocations);
    expect(parts.map((p) => [p.key, p.label, p.percent, p.amount, p.color])).toEqual([
      ["GOLD", "Altın", 30, 1740, "var(--chart-1)"],
      ["TRY_DEPOSIT", "TL mevduat", 25, 1450, "var(--chart-2)"],
      ["SPX", "S&P 500 endeksi", 25, 1450, "var(--chart-3)"],
      ["EUR", "Euro", 10, 580, "var(--chart-4)"],
      ["NVDA", "Nvidia hissesi", 10, 580, "var(--chart-5)"],
    ]);
    // each slot uses its own higher-contrast label ink
    expect(parts.map((p) => p.ink)).toEqual([1, 2, 3, 4, 5].map((slot) => `var(--chart-ink-${slot})`));
    expect(swatchFor(parts, "EUR")).toBe("var(--chart-4)");
  });

  it("draws nothing for 0 % and folds parts past eight into one grey block", () => {
    const many = Array.from({ length: 10 }, (_, i) => ({ asset: `A${i}`, percent: 10, amount: 100 }));
    const parts = allocationParts([...many, { asset: "ZERO", percent: 0, amount: 0 }]);
    expect(parts).toHaveLength(8);
    expect(parts[7]).toMatchObject({ key: "__other", label: "Diğer", percent: 30, amount: 300 });
    expect(parts.some((p) => p.key === "ZERO")).toBe(false);
    expect(swatchFor(parts, "A9")).toBe("var(--color-border-strong)");
  });

  it("prints a share inside a block only when it fits", () => {
    expect(labelFits(30, null, "%30")).toBe(true);
    expect(labelFits(10, null, "%10")).toBe(false);
    expect(labelFits(10, 600, "%10")).toBe(true); // 58 px block
    expect(labelFits(10, 300, "%10")).toBe(false); // 28 px block
  });
});
