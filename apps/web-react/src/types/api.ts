// Shapes of what the services send through the gateway. Field names are contracts (CLAUDE.md 8.1, 8.2,
// contracts/schemas/); only add optional fields here, never rename.

export type Segment = "LOW" | "MEDIUM" | "HIGH";
export type RiskLevel = Segment;

// ---- Identity ----------------------------------------------------------------------------------------------------

export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  // JWT "sub" claim (UUID) from the Identity service: the userId in every other service
  userId: string;
  email: string;
}

// ---- .NET Result envelope ------------------------------------------------------------------------------------------

export interface ApiResult<T> {
  data: T | null;
  success: boolean;
  message: string;
}

// ---- Finance Profile -----------------------------------------------------------------------------------------------

// Payment discipline answers (optional; null = not answered). Collected and shown, NOT part of the IQ score yet:
// a later scoring version may use them after validation.
export type BillsOnTime = "ALL" | "ALMOST_ALL" | "MOST" | "SOME" | "VERY_FEW";
export type MinimumPaymentMonths = "NONE" | "ONE_TWO" | "THREE_FIVE" | "SIX_PLUS" | "NO_CARD";
export type LatePayments = "NONE" | "ONCE" | "TWICE_OR_MORE";

export interface PaymentHabits {
  billsOnTime?: BillsOnTime | null;
  minimumPaymentMonths?: MinimumPaymentMonths | null;
  latePayments?: LatePayments | null;
}

export interface FinancialProfile {
  id: string;
  userId: string;
  monthlyIncome: number;
  monthlyExpenses: number;
  monthlyDebtPayment: number;
  totalDebt: number;
  cashReserve: number;
  investmentAmount: number;
  // optional since scoring v2 and not part of the score; the web app never sends it
  riskPreference: RiskLevel | null;
  // 1 = can wait years for a return, 5 = wants results right away
  impatienceLevel: number;
  // optional payment discipline answers; absent on servers that do not have them yet
  billsOnTime?: BillsOnTime | null;
  minimumPaymentMonths?: MinimumPaymentMonths | null;
  latePayments?: LatePayments | null;
  createdAt: string;
  updatedAt: string;
}

// body of PUT /api/Profiles/{userId}; amounts >= 0 and <= 999,999,999,999,999, monthlyIncome > 0.
// The payment habits are sent only when answered (null/undefined = left out of the body).
export interface ProfileInput extends PaymentHabits {
  monthlyIncome: number;
  monthlyExpenses: number;
  monthlyDebtPayment: number;
  totalDebt: number;
  cashReserve: number;
  investmentAmount: number;
  impatienceLevel: number;
}

export interface DebtPayoffMonth {
  month: number;
  openingBalance: number;
  interest: number;
  payment: number;
  principal: number;
  closingBalance: number;
}

// GET /api/Profiles/{userId}/debt-payoff (amortisation by dbo.fn_DebtPayoffSchedule, recursive CTE)
export interface DebtPayoff {
  totalDebt: number;
  monthlyPayment: number;
  // the rate actually used, 0.035 = 3.5 % a month
  monthlyInterestRate: number;
  // false: the installment does not cover the interest, or the debt is not paid within 600 months
  paidOff: boolean;
  months: number | null;
  totalInterest: number;
  totalPaid: number;
  schedule: DebtPayoffMonth[];
}

// ---- Financial IQ --------------------------------------------------------------------------------------------------

// v2 rules set the score (100 or 0); v3 labels only name the mechanism that shaped the factor points
export type AppliedRule = "VERY_HIGH_INCOME" | "VERY_HIGH_WEALTH" | "EXTREME_DEBT" | "SOLVENCY_CAP" | "WEALTH_RUNWAY";

// contracts/schemas/factor-breakdown.v2.schema.json. Keep it data-driven: a later version may bring other factor
// keys and a factorMaximums object (see factorRows in src/lib/labels.ts).
export interface FactorBreakdown {
  version?: string;
  // factor key -> points the user got
  factors: Record<string, number>;
  // optional, expected from a future version: factor key -> maximum points
  factorMaximums?: Record<string, number>;
  warnings: string[];
  // set when an extreme amount decided the score instead of the factors; null/absent otherwise
  appliedRule?: AppliedRule | null;
}

// POST /api/Profiles/{userId}/calculate-iq
export interface IqCalculation {
  score: number;
  segment: Segment;
  // exactly as the service sent it (send it on to /ai/explain-financial-iq unchanged); null when absent
  factorBreakdown: FactorBreakdown | null;
}

// GET /api/financial-iq/{userId}/latest
export interface IqResult extends IqCalculation {
  id: string;
  userId: string;
  createdAt: string;
  updatedAt: string;
  // changes on every recalculation; only compare for equality
  resultVersion?: number;
}

// GET /api/financial-iq/{userId}/history, oldest first
export interface IqTrendPoint {
  calculatedAt: string;
  score: number;
  segment: Segment;
  // difference to the previous calculation; null for the first one
  scoreChange: number | null;
  // average of this score and the two before it
  movingAverage3: number;
}

// GET /api/financial-iq/scoring-rules/current; rules = the rule set as JSON (segments, factors, special rules)
export interface ScoringRules {
  version: string;
  description: string;
  effectiveFrom: string;
  isActive: boolean;
  rules: unknown;
}

// ---- AI / RAG ------------------------------------------------------------------------------------------------------

export type FallbackReason =
  | "NO_BREAKDOWN"
  | "NO_DATA"
  | "DATA_UNAVAILABLE"
  | "LLM_UNAVAILABLE"
  | "EMPTY_OUTPUT"
  | "WRONG_LANGUAGE"
  | "UNVERIFIED_NUMBERS"
  | "BLOCKED_INPUT"
  | "UNSUPPORTED";

// common part of every AI response with generated text (schemas/common.py CheckedText)
export interface AiTextMeta {
  disclaimer: string;
  // model that wrote the text; null when the deterministic template was shown
  model: string | null;
  // true when every number in the text also appears in the data it was built from
  numbersVerified: boolean;
  fallbackUsed: boolean;
  fallbackReason: FallbackReason | null;
}

export interface ExplainRequest {
  score: number;
  segment: Segment;
  factorBreakdown?: FactorBreakdown;
}

export interface ExplainResponse extends AiTextMeta {
  explanation: string;
  persona: "coach";
}

export type AssistantMode = "router" | "tools";

export interface AskResponse extends AiTextMeta {
  answer: string;
  persona: "assistant";
  mode: AssistantMode;
  // what the answer is about: the intents the router picked or the tools the model called
  intents: string[];
}

export type Severity = "CRITICAL" | "WARNING" | "INFO";

export interface Alert {
  // stable code (icon, colour, link); message is the Turkish text to show
  code: string;
  severity: Severity;
  message: string;
}

// rule-based, no language model
export interface WarningsResponse {
  alerts: Alert[];
  disclaimer: string;
}

export interface TrendResponse extends AiTextMeta {
  explanation: string;
  persona: "coach";
  // how many calculations the explanation is based on
  points: number;
}

export interface PortfolioExplanationResponse extends AiTextMeta {
  explanation: string;
  persona: "coach";
  // the proposal was computed from an older IQ than the latest one: flagged, not explained
  stale: boolean;
  source: "sample" | "service";
}

// ---- Portfolio Service (contracts/schemas/portfolio-proposal.draft.schema.json, DRAFT) --------------------------

export type PortfolioOption = "INSTITUTION" | "CUSTOM" | "STANDARD" | "AINVEST";
export type InstitutionStyle = "ZIRAAT" | "ISBANK" | "YAPIKREDI";

export interface PortfolioProposal {
  proposalId: string;
  userId: string;
  createdAt: string;
  basedOn: {
    iqScore: number;
    segment: Segment;
    appliedRule: AppliedRule | null;
    iqCalculatedAt: string;
    scoringVersion: string;
    // IQ's resultVersion when the proposal was made (optional)
    resultVersion?: number | null;
  };
  preferences: {
    option: PortfolioOption;
    riskLevel: RiskLevel;
    institutionStyle?: InstitutionStyle;
    focusAssets?: string[];
    excludedAssets?: string[];
  };
  // chosen <= maxAllowed always (the IQ segment is the ceiling)
  risk: { chosen: RiskLevel; maxAllowed: RiskLevel };
  // sharePercent = clamp(IQ - 30, 0, 70); computed by the service, never in the frontend
  investable: { sharePercent: number; monthlyAmount: number; oneTimeAmount: number };
  // percent sums to 100; amount = share of investable.monthlyAmount
  // label (Turkish name) and oneTimeAmount are optional fields the service adds
  allocations: { asset: string; percent: number; amount: number; label?: string; oneTimeAmount?: number }[];
  // e.g. EXCLUDED_ASSET_REPLACED:BTC->GOLD, RESERVE_FIRST, FOCUS:BTC, PUBLISHED_ALLOCATION:ISBANK:2026-11
  reasons: string[];
  // optional, only INSTITUTION: where the published percentages come from
  source?: { name?: string; period?: string; url?: string } | null;
  // optional: the service's own check that the IQ was recalculated after this proposal
  stale?: boolean;
  disclaimer: string;
}
