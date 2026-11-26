import { afterEach, describe, expect, it, vi } from "vitest";
import { SAMPLE_SIGNAL_PLANS } from "../../mocks/signalPlans";
import { MemoryStorage } from "../../test/helpers";
import type { SignalPlan } from "../../types/signals";
import { browserStorage, readJson, userKey, writeJson } from "./safeStorage";
import { isPlanActive, sortPlans, zoneText } from "./signalLabels";
import { addToWatchlist, isWatched, loadWatchlist, parseWatchlist, removeFromWatchlist, saveWatchlist } from "./watchlist";

const plan = (asset: string): SignalPlan => SAMPLE_SIGNAL_PLANS.find((p) => p.asset === asset)!;

class ThrowingStorage extends MemoryStorage {
  override getItem(): string | null {
    throw new Error("SecurityError");
  }
  override setItem(): void {
    throw new Error("QuotaExceededError");
  }
}

afterEach(() => vi.unstubAllGlobals());

describe("watchlist", () => {
  const now = new Date("2026-11-24T10:00:00Z");

  it("adds a plan once (newest first) with a snapshot of its zone and removes it", () => {
    let items = addToWatchlist([], plan("GOLD"), now);
    expect(items).toEqual([
      {
        asset: "GOLD",
        assetName: "Altın (COMEX vadeli, GC=F)",
        quoteCurrency: "USD",
        direction: "SHORT",
        entryZone: { low: 4280, high: 4320 },
        planGeneratedAt: "2026-11-24T09:00:00Z",
        addedAt: "2026-11-24T10:00:00.000Z",
      },
    ]);
    expect(addToWatchlist(items, plan("GOLD"), now)).toBe(items);

    items = addToWatchlist(items, plan("SPX"), now);
    expect(items.map((i) => i.asset)).toEqual(["SPX", "GOLD"]);
    // no plan below the threshold: the view is followed, without a direction
    expect(items[0]).toMatchObject({ direction: null, entryZone: null });
    expect(isWatched(items, "SPX")).toBe(true);

    items = removeFromWatchlist(items, "SPX");
    expect(items.map((i) => i.asset)).toEqual(["GOLD"]);
    expect(isWatched(items, "SPX")).toBe(false);
  });

  it("survives a reload through localStorage", () => {
    const storage = new MemoryStorage();
    const items = addToWatchlist([], plan("BTC"), now);
    expect(saveWatchlist(storage, "w", items)).toBe(true);
    expect(loadWatchlist(storage, "w")).toEqual(items);
  });

  it("keeps working when storage throws, is missing or holds garbage", () => {
    const blocked = new ThrowingStorage();
    expect(saveWatchlist(blocked, "w", addToWatchlist([], plan("BTC"), now))).toBe(false);
    expect(loadWatchlist(blocked, "w")).toEqual([]);
    expect(saveWatchlist(null, "w", [])).toBe(false);
    expect(loadWatchlist(null, "w")).toEqual([]);

    const storage = new MemoryStorage();
    storage.setItem("w", "{not json");
    expect(loadWatchlist(storage, "w")).toEqual([]);
    storage.setItem("w", JSON.stringify({ asset: "BTC" }));
    expect(loadWatchlist(storage, "w")).toEqual([]);
  });

  it("drops malformed and duplicate items when parsing", () => {
    const parsed = parseWatchlist([
      { asset: "BTC", assetName: "Bitcoin", addedAt: "2026-11-24T10:00:00Z", direction: "LONG", entryZone: { low: 1, high: 2 } },
      { asset: "BTC", assetName: "dup", addedAt: "2026-11-24T10:00:00Z" },
      { asset: "DOGE", assetName: "x", addedAt: "2026-11-24T10:00:00Z" },
      { asset: "GOLD", assetName: "Altın", addedAt: "yesterday" },
      { asset: "SPX", assetName: "S&P", addedAt: "2026-11-24T10:00:00Z", direction: "UP", entryZone: { low: 1, high: 2 } },
      null,
    ]);
    expect(parsed.map((i) => [i.asset, i.direction, i.entryZone])).toEqual([
      ["BTC", "LONG", { low: 1, high: 2 }],
      ["SPX", null, null],
    ]);
    expect(parsed[1].quoteCurrency).toBe("USD");
  });
});

describe("safe storage", () => {
  it("returns null when the browser storage accessor throws", () => {
    vi.stubGlobal("localStorage", undefined);
    expect(browserStorage("local")).toBeNull();
    Object.defineProperty(globalThis, "sessionStorage", {
      configurable: true,
      get() {
        throw new Error("SecurityError");
      },
    });
    try {
      expect(browserStorage("session")).toBeNull();
    } finally {
      Reflect.deleteProperty(globalThis, "sessionStorage");
    }
  });

  it("reads and writes JSON and keys per user", () => {
    const storage = new MemoryStorage();
    expect(writeJson(storage, "k", { a: 1 })).toBe(true);
    expect(readJson(storage, "k")).toEqual({ a: 1 });
    expect(readJson(storage, "missing")).toBeNull();
    expect(userKey("base", "u-1")).toBe("base.u-1");
    expect(userKey("base", null)).toBe("base.anonymous");
  });
});

describe("signal labels", () => {
  it("orders the cards BTC, gold, S&P 500 and applies the threshold", () => {
    expect(sortPlans(SAMPLE_SIGNAL_PLANS).map((p) => p.asset)).toEqual(["BTC", "GOLD", "SPX"]);
    expect(isPlanActive(plan("GOLD"))).toBe(true);
    expect(isPlanActive(plan("SPX"))).toBe(false);
    expect(isPlanActive({ confirmation: { total: 70, threshold: 70, components: [] } })).toBe(true);
    expect(zoneText({ low: 86500, high: 88000 }, "USD")).toBe("86.500–88.000 USD");
  });
});
