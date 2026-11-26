// The risk ceiling (CLAUDE.md 8.4): the user picks the risk level after seeing the IQ, but only up to the IQ segment
// (LOW -> at most LOW, MEDIUM -> at most MEDIUM, HIGH -> at most HIGH). Levels above it are locked in the app and
// rejected by the Portfolio Service. The wording stays neutral: no "you said HIGH but..." messages.
import { LEVEL_LABELS } from "../../lib/labels";
import type { RiskLevel, Segment } from "../../types/api";

export const RISK_LEVELS: RiskLevel[] = ["LOW", "MEDIUM", "HIGH"];

export function riskRank(level: RiskLevel): number {
  return RISK_LEVELS.indexOf(level);
}

// the highest level the IQ segment allows; an unknown segment allows only LOW
export function maxRiskForSegment(segment: Segment | null | undefined): RiskLevel {
  return segment && RISK_LEVELS.includes(segment) ? segment : "LOW";
}

export function isRiskAllowed(level: RiskLevel, ceiling: RiskLevel): boolean {
  return riskRank(level) !== -1 && riskRank(level) <= riskRank(ceiling);
}

// a stored choice above today's ceiling (the score went down since) is shown as the ceiling
export function clampRisk(level: RiskLevel | null, ceiling: RiskLevel): RiskLevel | null {
  if (level === null || riskRank(level) === -1) return null;
  return isRiskAllowed(level, ceiling) ? level : ceiling;
}

export const RISK_TITLES: Record<RiskLevel, string> = { LOW: "Düşük", MEDIUM: "Orta", HIGH: "Yüksek" };

export const RISK_DESCRIPTIONS: Record<RiskLevel, string> = {
  LOW: "Daha az dalgalanma; korunaklı varlıklara ağırlık.",
  MEDIUM: "Korunaklı ve dalgalı varlıklar arasında denge.",
  HIGH: "Daha çok dalgalanma; getiri beklentisi de kayıp riski de daha yüksek.",
};

// neutral note under the levels
export function ceilingNote(ceiling: RiskLevel): string {
  if (ceiling === "HIGH") return "Finansal IQ segmentin üç risk seviyesinin hepsine izin veriyor.";
  return `IQ segmentin şu an en fazla ${LEVEL_LABELS[ceiling]} seviyesine izin veriyor; skorun yükseldikçe açılır.`;
}
