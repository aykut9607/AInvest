import { formatNumber } from "../../lib/format";
import { APPLIED_RULE_LABELS, factorRows, ruleSetsScore, type FactorRow } from "../../lib/labels";
import type { AppliedRule, FactorBreakdown } from "../../types/api";
import Card from "../Card";
import { FACTOR_TONE_LABELS, factorRatio, factorTone } from "./dashboardData";

// a v2 rule (100 or 0) wrote the factor points; a v3 label leaves them as computed, and an unknown rule is treated as v2
function overridingRule(rule: string | null | undefined): boolean {
  if (!rule) return false;
  return rule in APPLIED_RULE_LABELS ? ruleSetsScore(rule as AppliedRule) : true;
}

function FactorBar({ row }: { row: FactorRow }) {
  const points = formatNumber(row.points, 1);
  if (row.max === null) {
    // a factor this app does not know the maximum of: the points only, no bar that would have to guess a length
    return (
      <li className="factor" data-testid="factor-bar">
        <div className="factor-head">
          <span className="factor-label">{row.label}</span>
          <span className="factor-points">{`${points} puan`}</span>
        </div>
      </li>
    );
  }

  const tone = factorTone(row.points, row.max);
  const max = formatNumber(row.max);
  return (
    <li className="factor" data-testid="factor-bar">
      <div className="factor-head">
        <span className="factor-label">{row.label}</span>
        <span className="factor-points">{`${points} / ${max}`}</span>
      </div>
      <div
        className="factor-track"
        data-tone={tone}
        role="meter"
        aria-label={row.label}
        aria-valuemin={0}
        aria-valuemax={row.max}
        aria-valuenow={row.points}
        aria-valuetext={`${points} / ${max} puan, ${FACTOR_TONE_LABELS[tone]}`}
      >
        <div className="factor-fill" style={{ width: `${factorRatio(row.points, row.max) * 100}%` }} />
      </div>
    </li>
  );
}

// one bar per factor of the breakdown (data-driven: works for any factor keys the IQ service sends)
export default function FactorBreakdownCard({ breakdown, score }: { breakdown: FactorBreakdown | null; score: number }) {
  const rows = factorRows(breakdown);
  return (
    <Card
      title="Skor dökümü"
      subtitle={
        overridingRule(breakdown?.appliedRule)
          ? "Skoru özel kural belirledi; puanlar kurala göre yazıldı."
          : "Her faktörün aldığı puan; toplamları skoru verir."
      }
    >
      {rows.length === 0 ? (
        <p className="text-secondary">Bu sonuç için faktör dökümü yok.</p>
      ) : (
        <div className="stack">
          <ul className="factor-list">
            {rows.map((row) => (
              <FactorBar key={row.key} row={row} />
            ))}
          </ul>
          <p className="factor-total text-sm text-secondary">
            Toplam skor: <strong>{score}</strong> / 100
          </p>
          <p className="factor-legend text-xs text-muted">
            <span className="factor-legend-item" data-tone="good">güçlü (%70 ve üstü)</span>
            <span className="factor-legend-item" data-tone="warning">orta (%40–69)</span>
            <span className="factor-legend-item" data-tone="critical">zayıf (%40 altı)</span>
          </p>
        </div>
      )}
    </Card>
  );
}
