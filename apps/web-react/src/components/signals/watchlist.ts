// "Sanal takip listem": plans the user follows virtually. No order is ever sent anywhere; the list lives in this
// browser's localStorage only (per user) and works in memory when storage is unavailable.
import type { Direction, PriceZone, SignalAsset, SignalPlan } from "../../types/signals";
import { readJson, writeJson } from "./safeStorage";

export const WATCHLIST_STORAGE_KEY = "ainvest.signals.watchlist.v1";

const ASSETS: SignalAsset[] = ["BTC", "GOLD", "SPX"];
const DIRECTIONS: Direction[] = ["LONG", "SHORT"];

export interface WatchItem {
  asset: SignalAsset;
  // snapshot of the plan when it was added, so the list still reads right after the plan changes
  assetName: string;
  quoteCurrency: string;
  // null: the asset had no plan yet (confirmation below the threshold), the user follows the view
  direction: Direction | null;
  entryZone: PriceZone | null;
  planGeneratedAt: string;
  addedAt: string;
}

function isZone(value: unknown): value is PriceZone {
  if (!value || typeof value !== "object") return false;
  const zone = value as Record<string, unknown>;
  return typeof zone.low === "number" && Number.isFinite(zone.low) && typeof zone.high === "number" && Number.isFinite(zone.high);
}

function isDateText(value: unknown): value is string {
  return typeof value === "string" && value.length > 0 && !Number.isNaN(new Date(value).getTime());
}

// keeps only well-formed items, one per asset (the first one wins)
export function parseWatchlist(value: unknown): WatchItem[] {
  if (!Array.isArray(value)) return [];
  const seen = new Set<string>();
  const items: WatchItem[] = [];
  for (const raw of value) {
    if (!raw || typeof raw !== "object") continue;
    const item = raw as Record<string, unknown>;
    if (!ASSETS.includes(item.asset as SignalAsset) || seen.has(item.asset as string)) continue;
    if (typeof item.assetName !== "string" || !isDateText(item.addedAt)) continue;
    const direction = DIRECTIONS.includes(item.direction as Direction) ? (item.direction as Direction) : null;
    seen.add(item.asset as string);
    items.push({
      asset: item.asset as SignalAsset,
      assetName: item.assetName,
      quoteCurrency: typeof item.quoteCurrency === "string" ? item.quoteCurrency : "USD",
      direction,
      entryZone: direction && isZone(item.entryZone) ? item.entryZone : null,
      planGeneratedAt: isDateText(item.planGeneratedAt) ? item.planGeneratedAt : (item.addedAt as string),
      addedAt: item.addedAt as string,
    });
  }
  return items;
}

export function loadWatchlist(storage: Storage | null, key: string): WatchItem[] {
  return parseWatchlist(readJson(storage, key));
}

// true when the list reached the storage (false: it only lives in memory for this page view)
export function saveWatchlist(storage: Storage | null, key: string, items: WatchItem[]): boolean {
  return writeJson(storage, key, items);
}

export function isWatched(items: WatchItem[], asset: SignalAsset): boolean {
  return items.some((item) => item.asset === asset);
}

// newest first; adding an asset that is already on the list changes nothing
export function addToWatchlist(items: WatchItem[], plan: SignalPlan, now: Date = new Date()): WatchItem[] {
  if (isWatched(items, plan.asset)) return items;
  const item: WatchItem = {
    asset: plan.asset,
    assetName: plan.assetName,
    quoteCurrency: plan.quoteCurrency,
    direction: plan.plan?.direction ?? null,
    entryZone: plan.plan ? { low: plan.plan.entryZone.low, high: plan.plan.entryZone.high } : null,
    planGeneratedAt: plan.generatedAt,
    addedAt: now.toISOString(),
  };
  return [item, ...items];
}

export function removeFromWatchlist(items: WatchItem[], asset: SignalAsset): WatchItem[] {
  return items.filter((item) => item.asset !== asset);
}
