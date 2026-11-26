// 4.4 (AInvest önerisi): what the Portfolio Service's market module sends through the gateway
// (GET /api/portfolio/market/** and /api/portfolio/{userId}/market-plan; services/portfolio-service/api/routers/market.py).
// The service also sends a "disclaimer" string; the web UI does not show it (product decision, 25 Nov).

export type MarketKind = "SCALP" | "SCALP_SWING" | "SWING";
export type MarketDirection = "LONG" | "SHORT";

// one scoring category of a trigger (Fibonacci, Elliott, SFP, ...): its points and the rule that gave them
export interface MarketCategory {
  points: number;
  frame: string;
  // "Category|rule|variant"
  rule: string;
  // other time frames that support the same category
  also?: string[];
}

// a take profit or the stop that was filled
export interface MarketFill {
  zone: string;
  price: number;
  units: number;
  atTsi: string;
  pnlUsd: number;
}

export interface MarketTrade {
  id: string;
  asset: string;
  direction: MarketDirection;
  kind: MarketKind;
  status: "OPEN" | "PARTIAL" | "CLOSED";
  // "dd.MM.yyyy HH:mm" in Turkish time, already formatted by the service
  openedAtTsi: string;
  closedAtTsi: string | null;
  durationHours: number;
  entry: number;
  leverage: number;
  stop: number;
  stopPercent: number;
  stopNow: number;
  steps: { zone: string; price: number; units: number }[];
  unitsLeft: number;
  marginUsd: number;
  notionalUsd: number;
  balanceBefore: number;
  balanceAfter: number | null;
  takeProfits: MarketFill[];
  stopped: MarketFill | null;
  exitReason: string | null;
  pnlUsd: number;
  roiPercent: number | null;
  resultR: number | null;
  openPnlUsd: number;
  lastPrice?: number;
  maxProfit: { price?: number; percent: number; roiPercent: number };
  maxLoss: { percent: number };
  score: number;
  triggerFrame: string;
  trigger?: string[];
  categories: Record<string, MarketCategory>;
}

export interface MarketTradeDetail extends MarketTrade {
  // time frame -> "Category|rule|variant" tags (the backtest detail may leave it out)
  confirmations?: Record<string, string[]>;
  analysis?: { trader?: string; standard?: string };
}

// a trade the engine would have opened while it was off; never touches the account
export interface MarketMissed {
  id: string;
  asset: string;
  direction: MarketDirection;
  kind: MarketKind;
  atTsi: string;
  notedAtTsi: string;
  entry: number;
  stop: number;
  stopPercent: number;
  leverage: number;
  score: number;
  triggerFrame: string;
  categories: Record<string, MarketCategory>;
  wouldBe: {
    status: "OPEN" | "CLOSED";
    exitReason: string | null;
    resultR: number | null;
    roiPercent: number;
    maxProfitRoi: number;
    closedAtTsi: string | null;
  };
}

// the virtual account (USD); every trade is opened from the current balance
export interface MarketAccount {
  iqScore: number;
  startBalance: number;
  balance: number;
  openPnlUsd: number;
  equity: number;
  percent: number;
  openTrades: number;
  won: number;
  lost: number;
  closedTrades: number;
  missed: number;
}

export interface MarketGroup {
  n: number;
  won: number;
  lost: number;
  averageR: number;
}

export interface MarketPerformance {
  n: number;
  won: number;
  lost: number;
  winRate: number | null;
  averageR: number | null;
  profitFactor: number | null;
  longestLosingStreak: number | null;
  byKind: Record<string, MarketGroup>;
  byExit: Record<string, MarketGroup>;
  byRule: Record<string, MarketGroup>;
}

export interface MarketTrigger {
  time: number;
  direction: MarketDirection;
  triggerFrame: string;
  price: number;
  score: number;
  // null: the score did not reach any kind's limit
  kind: MarketKind | null;
  categories: Record<string, MarketCategory>;
  noPlan?: string;
}

// the engine's current view of one asset (BTC, GOLD, SPX)
export interface MarketViewItem {
  asset: string;
  status: "NO_VIEW" | "CONFIRMED";
  scannedAt: string | null;
  scan: { problem: string | null; dataUntil: number; triggers: MarketTrigger[] } | null;
  // category -> points it can give
  weights: Record<string, number>;
  // the score a trigger needs for each kind
  limits: Record<MarketKind, number>;
}

export interface MarketStats {
  n: number;
  won?: number;
  lost?: number;
  winRate?: number;
  averageR?: number;
  profitFactor?: number | null;
  longestLosingStreak?: number;
  medianHours?: number;
}

export interface MarketBacktestAccount {
  start: number;
  end: number;
  percent: number;
  maxDrawdownPercent?: number;
}

// the last year played again with the same rules: each asset alone, all three from one account ("ALL"),
// and the same run with shuffled entries as the control
export interface MarketBacktest {
  // epoch seconds
  from: number;
  to: Record<string, number>;
  real: Record<string, { all: MarketStats; account: MarketBacktestAccount }>;
  control: Record<string, { all: MarketStats; account: MarketBacktestAccount }>;
  // the common account after every closed trade
  curve: { time: number; balance: number }[];
  // newest first
  trades: MarketTrade[];
}

// the open virtual trades sized for this user's IQ
export interface MarketPlanItem extends MarketTrade {
  size: { marginPercent: number; leverage: number; notionalPercent: number; riskPercent: number };
}

export interface MarketPlan {
  iqScore: number;
  items: MarketPlanItem[];
}

export interface MarketOverview {
  account: MarketAccount | null;
  view: MarketViewItem[];
  trades: MarketTrade[];
  missed: MarketMissed[];
  performance: MarketPerformance | null;
}
