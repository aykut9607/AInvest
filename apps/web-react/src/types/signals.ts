// DRAFT - NOT A CONTRACT. Local shape for the 4.4 "AInvest önerisi" screens until the Portfolio Service's 4.4 module
// (services/portfolio-service/signals, Aykut) publishes its own schema. Built from CLAUDE.md 8.4 and 5.8b:
// rule-based confirmation score (>= 70 -> plan), a conditional plan instead of an order, levels, main and alternative
// wave model, confidence text from the backtest calibration. Replace with the real schema when it exists.

export type SignalAsset = "BTC" | "GOLD" | "SPX";
export type Timeframe = "1W" | "1D" | "4h" | "1h" | "45m" | "30m" | "15m";
export type Direction = "LONG" | "SHORT";
export type MarketBias = "BULLISH" | "BEARISH" | "NEUTRAL";

export interface PriceZone {
  low: number;
  high: number;
}

// higher-timeframe view of the market (HTF 1W/1D/4h)
export interface MarketView {
  bias: MarketBias;
  timeframes: Timeframe[];
  // Turkish, shown as is
  summary: string;
}

// lower-timeframe confirmation the plan waits for (LTF 4h/1h): e.g. 1h SFP, RSI P.U / N.U divergence, CVD
export type LtfSignal = "SFP" | "RSI_DIVERGENCE" | "CVD_DIVERGENCE" | "CLOSE_CONFIRMATION";

export interface LtfConfirmation {
  timeframes: Timeframe[];
  signals: LtfSignal[];
  description: string;
}

// "if price reaches the zone, look for LTF confirmation, then <direction>" - never an order
export interface ConditionalPlan {
  direction: Direction;
  entryZone: PriceZone;
  ltfConfirmation: LtfConfirmation;
  targets: number[];
  stop: number;
  description: string;
}

export interface SignalLevels {
  // the view is wrong beyond this price
  invalidation: number;
  // the closer level that cancels the current setup (the view may still hold)
  microInvalidation: number;
  keyLevel: number;
}

export type ModelKind = "ELLIOTT_IMPULSE" | "ELLIOTT_CORRECTION" | "HARMONIC" | "FIBONACCI" | "RANGE";

export interface WaveModel {
  kind: ModelKind;
  name: string;
  description: string;
  // how well the swings fit the model, 0-100
  fit: number;
}

export interface ConfirmationComponent {
  // HTF_TREND, FIB_ZONE, RSI_DIVERGENCE, CVD_DIVERGENCE, SFP, REGIME_VETO ...
  code: string;
  label: string;
  points: number;
  max: number;
}

export interface ConfirmationScore {
  // 0-100; a plan is shown only at or above threshold
  total: number;
  threshold: number;
  components: ConfirmationComponent[];
}

export interface BacktestConfidence {
  // Turkish text built from the calibration, shown as is
  text: string;
  // distinct setups in the test period (not rows: touch/close/close+ltf copies count once)
  sampleSize: number;
  // share of successful setups and its Wilson 95 % interval, 0-1
  hitRate: number | null;
  interval95: [number, number] | null;
  period: string;
}

export interface SignalPlan {
  asset: SignalAsset;
  assetName: string;
  quoteCurrency: "USD";
  generatedAt: string;
  lastPrice: number;
  view: MarketView;
  // null when the confirmation score is below the threshold: nothing to plan, keep watching
  plan: ConditionalPlan | null;
  levels: SignalLevels;
  mainModel: WaveModel;
  alternativeModel: WaveModel | null;
  confirmation: ConfirmationScore;
  backtest: BacktestConfidence;
  // "yatırım tavsiyesi değildir" (YTD)
  disclaimer: string;
  // true for the mock data in src/mocks/signalPlans.ts
  isSample: boolean;
}
