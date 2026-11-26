export type Level = "LOW" | "MEDIUM" | "HIGH";
export type Option = "INSTITUTION" | "CUSTOM" | "STANDARD" | "AINVEST";
export type Style = "ZIRAAT" | "ISBANK" | "YAPIKREDI";

export interface Source {
  name: string;
  period: string;
  url: string;
}

export interface InvestableBasis {
  monthlyIncome: number;
  monthlyExpenses: number;
  monthlyDebtPayment: number;
  monthlySurplus: number;
  cashReserve: number;
  investmentAmount: number;
  reserve: number;
  emergencyFund: number;
  freeCash: number;
  reserveMonths: number;
}

export interface Investable {
  sharePercent: number;
  monthlyAmount: number;
  oneTimeAmount: number;
  basis?: InvestableBasis | null;
  reasons?: string[];
}

export interface PortfolioOptions {
  iqScore: number;
  segment: Level;
  maxRisk: Level;
  investable: Investable;
  options: Option[];
  unavailableOptions: Option[];
  institutionStyleInfo: { code: Style; label: string; description: string; source: Source }[];
  assetInfo: { code: string; label: string }[];
  reasons: string[];
}

export interface Preferences {
  option: Option;
  riskLevel: Level;
  institutionStyle?: Style | null;
  focusAssets?: string[];
  excludedAssets?: string[];
}

export interface Proposal {
  createdAt: string;
  basedOn: { iqScore: number; segment: Level; iqCalculatedAt: string; scoringVersion: string };
  preferences: Preferences;
  risk: { chosen: Level; maxAllowed: Level };
  investable: Investable;
  allocations: { asset: string; label: string; percent: number; amount: number; oneTimeAmount: number }[];
  reasons: string[];
  source: Source | null;
  stale: boolean;
  disclaimer: string;
}

export interface Explanation {
  explanation: string;
  disclaimer?: string;
  model?: string | null;
  numbersVerified?: boolean;
  fallbackUsed?: boolean;
  stale?: boolean;
  source?: string;
}

export interface IqResult {
  score: number;
  segment: Level;
  factorBreakdown: { version?: string; factors: Record<string, number>; warnings: string[]; appliedRule?: string | null; adjustment?: { rule: string; fromFactors: number; score: number } | null } | null;
  createdAt: string;
  updatedAt: string | null;
  resultVersion?: number;
}

// ---------- 4.4

export type Kind = "SCALP" | "SCALP_SWING" | "SWING";

export interface Category {
  points: number;
  frame: string;
  rule: string;
  also?: string[];
}

export interface Fill {
  zone: string;
  price: number;
  units: number;
  atTsi: string;
  pnlUsd: number;
}

export interface Trade {
  id: string;
  asset: string;
  direction: "LONG" | "SHORT";
  kind: Kind;
  status: "OPEN" | "PARTIAL" | "CLOSED";
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
  takeProfits: Fill[];
  stopped: Fill | null;
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
  trigger: string[];
  categories: Record<string, Category>;
}

export interface TradeDetail extends Trade {
  confirmations: Record<string, string[]>;
  analysis: { trader: string; standard: string };
}

export interface Missed {
  id: string;
  asset: string;
  direction: "LONG" | "SHORT";
  kind: Kind;
  atTsi: string;
  notedAtTsi: string;
  entry: number;
  stop: number;
  stopPercent: number;
  leverage: number;
  score: number;
  triggerFrame: string;
  categories: Record<string, Category>;
  wouldBe: { status: "OPEN" | "CLOSED"; exitReason: string | null; resultR: number | null; roiPercent: number; maxProfitRoi: number; closedAtTsi: string | null; fills: { zone: string; price: number; units: number; atTsi: string }[] };
}

export interface Account {
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

export interface Group {
  n: number;
  won: number;
  lost: number;
  averageR: number;
}

export interface Performance {
  n: number;
  won: number;
  lost: number;
  winRate: number | null;
  averageR: number | null;
  profitFactor: number | null;
  longestLosingStreak: number | null;
  byKind: Record<string, Group>;
  byExit: Record<string, Group>;
  byRule: Record<string, Group>;
}

export interface ViewItem {
  asset: string;
  status: "NO_VIEW" | "CONFIRMED";
  scannedAt: string | null;
  scan: {
    problem: string | null;
    dataUntil: number;
    triggers: { time: number; direction: "LONG" | "SHORT"; triggerFrame: string; price: number; score: number; kind: Kind | null; categories: Record<string, Category>; noPlan?: string }[];
  } | null;
  weights: Record<string, number>;
  limits: Record<Kind, number>;
}

export interface Stats {
  n: number;
  won?: number;
  lost?: number;
  winRate?: number;
  averageR?: number;
  errorR?: number;
  profitFactor?: number | null;
  longestLosingStreak?: number;
  medianHours?: number;
}

export interface Rehearsal {
  from: number;
  to: Record<string, number>;
  real: Record<string, { all: Stats; account: { start: number; end: number; percent: number; maxDrawdownPercent: number } } & Record<Kind, Stats>>;
  control: Record<string, { all: Stats; account: { end: number } }>;
  curve: { time: number; balance: number }[];
  trades: Trade[];
  disclaimer: string;
}
