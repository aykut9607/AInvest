// The user's portfolio choices (option 4.1-4.4, risk level, option details). Kept in this tab's sessionStorage until
// the Portfolio Service exists; then they are sent to it (field names follow the draft schema's `preferences`).
import type { InstitutionStyle, PortfolioOption, RiskLevel } from "../../types/api";
import { readJson, writeJson } from "../signals/safeStorage";
import { RISK_LEVELS } from "./risk";

export const PREFERENCES_STORAGE_KEY = "ainvest.portfolio.preferences.v1";

export interface PortfolioPreferences {
  // null until the user picks one
  option: PortfolioOption | null;
  riskLevel: RiskLevel | null;
  institutionStyle: InstitutionStyle | null;
  // 4.2: the areas the portfolio should focus on
  focusAssets: string[];
  // 4.3: assets of the standard basket the user does not want (the service puts alternatives in their place)
  excludedAssets: string[];
}

export const EMPTY_PREFERENCES: PortfolioPreferences = {
  option: null,
  riskLevel: null,
  institutionStyle: null,
  focusAssets: [],
  excludedAssets: [],
};

export interface OptionInfo {
  value: PortfolioOption;
  // the roadmap number shown on the card
  code: string;
  description: string;
}

export const OPTIONS: OptionInfo[] = [
  {
    value: "INSTITUTION",
    code: "4.1",
    description: "Bir kurumun yatırım tarzına benzeyen hazır dağılım: koruyucu, dengeli ya da agresif.",
  },
  {
    value: "CUSTOM",
    code: "4.2",
    description: "İlgilendiğin alanları seç; dağılım o alanlara ağırlık verir.",
  },
  {
    value: "STANDARD",
    code: "4.3",
    description: "Farklı varlıklardan oluşan standart sepet; istemediğin varlıkların yerine alternatif konur.",
  },
  {
    value: "AINVEST",
    code: "4.4",
    description: "Geçmiş verilerle test edilen kural tabanlı piyasa planları (Bitcoin, altın, S&P 500).",
  },
];

export const INSTITUTION_STYLES: { value: InstitutionStyle; description: string }[] = [
  { value: "ZIRAAT", description: "Mevduat ve emtia ağırlıklı." },
  { value: "ISBANK", description: "S&P 500 ve mevduat dengesi." },
  { value: "YAPIKREDI", description: "S&P 500 ve yapay zekâ şirketleri ağırlıklı." },
];

// 4.2 focus areas (codes the AI service and lib/labels.ts know)
export const FOCUS_ASSETS = ["GOLD", "SILVER", "TRY_DEPOSIT", "TRY_BOND", "SPX", "NDQ", "BIST100", "EUR", "USD", "AI_STOCKS", "BTC", "ETH"];

// 4.3 basket. ASSUMPTION until the Portfolio Service defines it: the assets of the draft schema's example (its
// allocation plus the excluded BTC).
export const STANDARD_BASKET = ["GOLD", "TRY_DEPOSIT", "SPX", "EUR", "NVDA", "BTC"];

const OPTION_VALUES = OPTIONS.map((o) => o.value);
const STYLE_VALUES = INSTITUTION_STYLES.map((s) => s.value);

function assetList(value: unknown, allowed: string[]): string[] {
  if (!Array.isArray(value)) return [];
  return [...new Set(value.filter((v): v is string => typeof v === "string" && allowed.includes(v)))];
}

// anything unreadable or unknown falls back to "not chosen"
export function parsePreferences(value: unknown): PortfolioPreferences {
  if (!value || typeof value !== "object") return EMPTY_PREFERENCES;
  const v = value as Record<string, unknown>;
  return {
    option: OPTION_VALUES.includes(v.option as PortfolioOption) ? (v.option as PortfolioOption) : null,
    riskLevel: RISK_LEVELS.includes(v.riskLevel as RiskLevel) ? (v.riskLevel as RiskLevel) : null,
    institutionStyle: STYLE_VALUES.includes(v.institutionStyle as InstitutionStyle) ? (v.institutionStyle as InstitutionStyle) : null,
    focusAssets: assetList(v.focusAssets, FOCUS_ASSETS),
    excludedAssets: assetList(v.excludedAssets, STANDARD_BASKET),
  };
}

export function loadPreferences(storage: Storage | null, key: string): PortfolioPreferences {
  return parsePreferences(readJson(storage, key));
}

export function savePreferences(storage: Storage | null, key: string, preferences: PortfolioPreferences): boolean {
  return writeJson(storage, key, preferences);
}

export function toggleAsset(list: string[], asset: string): string[] {
  return list.includes(asset) ? list.filter((a) => a !== asset) : [...list, asset];
}

// what is still missing before the choice is complete (Turkish, for the summary); [] when complete
export function missingChoices(preferences: PortfolioPreferences): string[] {
  const missing: string[] = [];
  if (!preferences.option) missing.push("portföy türü");
  if (preferences.option === "INSTITUTION" && !preferences.institutionStyle) missing.push("kurum tarzı");
  if (preferences.option === "CUSTOM" && preferences.focusAssets.length === 0) missing.push("en az bir odak alanı");
  if (!preferences.riskLevel) missing.push("risk seviyesi");
  return missing;
}
