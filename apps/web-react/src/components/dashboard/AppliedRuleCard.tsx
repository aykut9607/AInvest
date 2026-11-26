import { APPLIED_RULE_LABELS, APPLIED_RULE_THRESHOLDS, ruleSetsScore } from "../../lib/labels";
import type { AppliedRule } from "../../types/api";
import Card from "../Card";

// Shown when factorBreakdown.appliedRule is set. A v2 rule set the score itself (100 or 0) instead of the factors;
// a v3 label (SOLVENCY_CAP, WEALTH_RUNWAY) names the mechanism that shaped the factor points, which still add up.
export default function AppliedRuleCard({ rule }: { rule: string }) {
  const known = rule in APPLIED_RULE_LABELS ? (rule as AppliedRule) : null;
  const label = known ? APPLIED_RULE_LABELS[known] : null;
  const setsScore = known ? ruleSetsScore(known) : true;

  return (
    <Card title={setsScore ? "Bu skor nasıl belirlendi?" : "Skoru etkileyen durum"} tone="muted" className="rule-card">
      <div className="stack-sm">
        <p className="rule-card-title">{label ? label.title : `Özel kural: ${rule}`}</p>
        {label ? <p>{label.description}</p> : null}
        {known ? <p className="text-sm text-secondary">{APPLIED_RULE_THRESHOLDS[known]}</p> : null}
        <p className="text-sm text-muted">
          {setsScore
            ? "Skoru beş faktör değil bu kural belirledi; faktör çubukları kurala göre tam ya da sıfır puan gösterir."
            : "Skor yine beş faktörün toplamı; bu durum faktör puanlarının nasıl hesaplandığını etkiledi."}
        </p>
      </div>
    </Card>
  );
}
