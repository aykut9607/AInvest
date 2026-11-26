import type { ApiResult } from "../types/api";
import type {
  MarketAccount,
  MarketBacktest,
  MarketMissed,
  MarketOverview,
  MarketPerformance,
  MarketPlan,
  MarketTrade,
  MarketTradeDetail,
  MarketViewItem,
} from "../types/market";
import { authorizedRequest, currentUserId } from "./authorizedRequest";
import { errorFrom, type CallOptions } from "./http";

// 4.4 (AInvest önerisi) from the Portfolio Service's market module, through the gateway.
// GET /api/portfolio/market/** needs a valid token only (the same view for every user); the per-user sizing is
// /api/portfolio/{userId}/market-plan (own user only). The service's "disclaimer" field is ignored on purpose.

const MARKET = "/api/portfolio/market";

// the envelope's data, or null on 404 ("nothing stored yet")
async function getData<T>(path: string, fallback: string, options: CallOptions): Promise<T | null> {
  const response = await authorizedRequest<ApiResult<T>>(path, options);
  if (response.status === 404) return null;
  const body = response.body;
  if (response.status !== 200 || !body?.success || body.data === null || body.data === undefined) {
    throw errorFrom(response, fallback);
  }
  return body.data;
}

const itemsOf = <T>(data: { items?: T[] } | null): T[] => (Array.isArray(data?.items) ? data.items : []);

// everything the 4.4 page shows at once; empty lists (and a null account/performance) when nothing exists yet
export async function getMarketOverview(options: CallOptions = {}): Promise<MarketOverview> {
  const [account, view, trades, missed, performance] = await Promise.all([
    getData<MarketAccount>(`${MARKET}/account`, "Sanal kasa yüklenemedi.", options),
    getData<{ items: MarketViewItem[] }>(`${MARKET}/view`, "Piyasa görüşü yüklenemedi.", options),
    getData<{ items: MarketTrade[] }>(`${MARKET}/trades?limit=200`, "Sanal işlemler yüklenemedi.", options),
    getData<{ items: MarketMissed[] }>(`${MARKET}/missed`, "Kaçırılan işlemler yüklenemedi.", options),
    getData<MarketPerformance>(`${MARKET}/performance`, "İstatistik yüklenemedi.", options),
  ]);
  return { account, view: itemsOf(view), trades: itemsOf(trades), missed: itemsOf(missed), performance };
}

export type TradeSource = "live" | "backtest";

// one trade with its confirmations and the two written analyses; backtest ids look like "year-12"
export async function getMarketTrade(id: string, source: TradeSource, options: CallOptions = {}): Promise<MarketTradeDetail | null> {
  const base = source === "backtest" ? `${MARKET}/backtest` : `${MARKET}/trades`;
  return getData<MarketTradeDetail>(`${base}/${encodeURIComponent(id)}`, "İşlem yüklenemedi.", options);
}

// the last year replayed with the same rules; null when the service has no stored backtest (404)
export async function getMarketBacktest(options: CallOptions = {}): Promise<MarketBacktest | null> {
  const data = await getData<MarketBacktest>(`${MARKET}/backtest`, "Geçmiş test yüklenemedi.", options);
  return data ? { ...data, curve: data.curve ?? [], trades: data.trades ?? [] } : null;
}

// the open virtual trades sized for the signed-in user's IQ; null when the IQ (or the plan) is not there yet
export async function getMarketPlan(options: CallOptions = {}): Promise<MarketPlan | null> {
  const data = await getData<MarketPlan>(
    `/api/portfolio/${encodeURIComponent(currentUserId())}/market-plan`,
    "Kişisel plan yüklenemedi.",
    options
  );
  return data ? { iqScore: data.iqScore, items: data.items ?? [] } : null;
}
