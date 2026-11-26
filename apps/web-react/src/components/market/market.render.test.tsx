import { renderToString as renderRaw } from "react-dom/server";
import { describe, expect, it } from "vitest";
import type { MarketBacktest, MarketOverview, MarketTradeDetail } from "../../types/market";
import { AccountStats, BacktestView, Overview, StatsView } from "./MarketView";
import { TradeBody } from "./TradeDrawer";

// server render without the <!-- --> markers React puts between adjacent text nodes
const renderToString = (node: Parameters<typeof renderRaw>[0]) => renderRaw(node).replace(/<!-- -->/g, "");

const account = { iqScore: 87, startBalance: 1000, balance: 1000, openPnlUsd: 0, equity: 1000, percent: 0, openTrades: 0, won: 0, lost: 0, closedTrades: 0, missed: 0 };

const trade: MarketTradeDetail = {
  id: "year-1", asset: "BTC", direction: "LONG", kind: "SCALP", status: "CLOSED",
  openedAtTsi: "19.11.2026 23:30", closedAtTsi: "20.11.2026 00:30", durationHours: 1,
  entry: 61897.91, leverage: 25, stop: 61699.22, stopPercent: 0.321, stopNow: 61699.22,
  steps: [{ zone: "HALF_AT_SCALP_TP", price: 63080.35, units: 50 }, { zone: "TP1", price: 63292.9, units: 50 }],
  unitsLeft: 0, marginUsd: 15.48, notionalUsd: 387.04, balanceBefore: 703.72, balanceAfter: 702.09,
  takeProfits: [], stopped: { zone: "STOP", price: 61699.22, units: 100, atTsi: "20.11.2026 00:30", pnlUsd: -1.44 },
  exitReason: "STOP", pnlUsd: -1.63, roiPercent: -10.5, resultR: -1.312, openPnlUsd: 0,
  maxProfit: { percent: 0.7, roiPercent: 17.5 }, maxLoss: { percent: -0.32 }, score: 32.5, triggerFrame: "15m",
  categories: { Elliott: { points: 14.76, frame: "6h", rule: "Elliott|12345 sonu|3. dalga uzayan" } },
  confirmations: { "1h": ["SFP|Tek mum|"] },
  analysis: { standard: "Standart yorum metni.", trader: "Trader yorum metni." },
};

describe("4.4 market view", () => {
  it("shows the empty state, not an error, when the engine has no trades yet", () => {
    const empty: MarketOverview = { account, view: [], trades: [], missed: [], performance: null };
    const html = renderToString(
      <>
        <AccountStats account={empty.account} />
        <Overview data={empty} plan={null} onOpen={() => {}} />
        <StatsView p={null} />
      </>
    );
    expect(html).toContain("Sanal kasa");
    expect(html).toContain("1.000,00 $");
    expect(html).toContain("Henüz plan yok");
    expect(html).toContain("Henüz kapanan işlem yok");
    expect(html).not.toContain("tavsiyesi değildir");
    expect(html).not.toContain("Örnek veri");
  });

  it("lists the backtest per asset next to the shuffled control, and its trades", () => {
    const stats = { n: 111, won: 38, lost: 73, winRate: 0.342, averageR: -0.26, profitFactor: 0.62 };
    const backtest: MarketBacktest = {
      from: 1764027900,
      to: { BTC: 1795563900 },
      real: { BTC: { all: stats, account: { start: 1000, end: 842.49, percent: -15.8, maxDrawdownPercent: 16.7 } } },
      control: { BTC: { all: stats, account: { start: 1000, end: 919.02, percent: -8.1 } } },
      curve: [],
      trades: [trade],
    };
    const html = renderToString(<BacktestView backtest={backtest} onOpen={() => {}} />);
    expect(html).toContain("Bitcoin");
    expect(html).toContain("%34,2");
    expect(html).toContain("−15,8 %");
    expect(html).toContain("−8,1 %");
    expect(html).toContain("19.11.2026 23:30");
    expect(renderToString(<BacktestView backtest={null} onOpen={() => {}} />)).toContain("Geçmiş test yok");
  });

  it("shows a trade's plan, fills, score bars, analysis and confirmations", () => {
    const html = renderToString(<TradeBody t={trade} />);
    expect(html).toContain("Plan ve gerçekleşen");
    expect(html).toContain("Yarı kâr (Scalp TP)");
    expect(html).toContain("−1,63 $");
    expect(html).toContain("12345 sonu (3. dalga uzayan)");
    expect(html).toContain("Standart yorum metni.");
    expect(html).toContain("SFP: Tek mum");
  });
});
