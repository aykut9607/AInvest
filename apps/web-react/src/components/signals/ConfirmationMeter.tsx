import Badge from "../Badge";
import type { ConfirmationScore } from "../../types/signals";

function clampPercent(value: number, max: number): number {
  if (!Number.isFinite(value) || !Number.isFinite(max) || max <= 0) return 0;
  return Math.min(100, Math.max(0, (value / max) * 100));
}

// Rule-based confirmation score as a meter (dataviz: one value against a limit = meter, not a chart). The fill and its
// track are two steps of the same blue ramp; the threshold is a tick across the track with its number under it. The
// state ("Plan aktif" / "Onay bekleniyor") is a labelled badge, so nothing depends on colour alone.
export default function ConfirmationMeter({ confirmation }: { confirmation: ConfirmationScore }) {
  const { total, threshold } = confirmation;
  const active = total >= threshold;
  const fill = clampPercent(total, 100);
  const tick = clampPercent(threshold, 100);
  const stateText = active ? "Plan aktif" : "Onay bekleniyor";

  return (
    <div className="confirmation">
      <div className="confirmation-head">
        <span className="confirmation-label">Onay puanı</span>
        <span className="confirmation-value">
          {total}
          <span className="confirmation-of"> / 100</span>
        </span>
        <Badge tone={active ? "good" : "info"} dot>
          {stateText}
        </Badge>
      </div>
      <div
        className="meter"
        role="meter"
        aria-label="Onay puanı"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={total}
        aria-valuetext={`${total} / 100, eşik ${threshold}: ${stateText.toLocaleLowerCase("tr-TR")}`}
      >
        <div className="meter-track" aria-hidden="true">
          <div className="meter-fill" style={{ width: `${fill}%` }} />
        </div>
        <div className="meter-tick" style={{ left: `${tick}%` }} aria-hidden="true" />
        <div className="meter-scale" aria-hidden="true">
          <span>0</span>
          <span className="meter-tick-label" style={{ left: `${tick}%` }}>
            Eşik {threshold}
          </span>
          <span>100</span>
        </div>
      </div>
      <p className="text-xs text-muted">
        {active
          ? `Puan eşiğin (${threshold}) üstünde: koşullu plan gösteriliyor.`
          : `Puan eşiğin (${threshold}) altında: plan yok, onay bekleniyor.`}
      </p>
    </div>
  );
}

// the points behind the score: one thin bar per component against its own maximum (a meter list)
export function ConfirmationBreakdown({ confirmation }: { confirmation: ConfirmationScore }) {
  if (confirmation.components.length === 0) return null;
  return (
    <ul className="meter-list">
      {confirmation.components.map((component) => (
        <li key={component.code} className="meter-list-row">
          <span className="meter-list-name">{component.label}</span>
          <span className="meter-list-value tabular">
            {component.points}/{component.max}
          </span>
          <span
            className="meter-list-bar"
            role="meter"
            aria-label={component.label}
            aria-valuemin={0}
            aria-valuemax={component.max}
            aria-valuenow={component.points}
            aria-valuetext={`${component.points} / ${component.max}`}
          >
            <span className="meter-list-fill" style={{ width: `${clampPercent(component.points, component.max)}%` }} />
          </span>
        </li>
      ))}
    </ul>
  );
}
