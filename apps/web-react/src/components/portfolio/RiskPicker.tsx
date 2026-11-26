import { useId } from "react";
import type { RiskLevel } from "../../types/api";
import { RISK_DESCRIPTIONS, RISK_LEVELS, RISK_TITLES, ceilingNote, isRiskAllowed } from "./risk";

function LockIcon() {
  return (
    <svg className="risk-lock" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
      <rect x="5" y="11" width="14" height="10" rx="2" />
      <path d="M8 11V8a4 4 0 0 1 8 0v3" strokeLinecap="round" />
    </svg>
  );
}

export interface RiskPickerProps {
  value: RiskLevel | null;
  ceiling: RiskLevel;
  onChange: (level: RiskLevel) => void;
  // replaces the default ceiling note (the service's ceiling is below the segment)
  note?: string;
  // sentences explaining a lowered ceiling (the service's CEILING_* reasons)
  reasons?: string[];
}

// Radio group with a lock on the levels above the IQ ceiling (SegmentedControl has no per-option disabled state).
// Locked levels are disabled inputs, so keyboards skip them and screen readers announce them as unavailable.
export default function RiskPicker({ value, ceiling, onChange, note, reasons = [] }: RiskPickerProps) {
  const name = useId();
  const noteId = `${name}-note`;

  return (
    <fieldset className="risk-picker" aria-describedby={noteId}>
      <legend className="field-label">Risk seviyesi</legend>
      <div className="risk-options">
        {RISK_LEVELS.map((level) => {
          const allowed = isRiskAllowed(level, ceiling);
          return (
            <label key={level} className={`risk-option${allowed ? "" : " is-locked"}`}>
              <input
                type="radio"
                name={name}
                value={level}
                checked={value === level}
                disabled={!allowed}
                onChange={() => onChange(level)}
                aria-label={allowed ? `${RISK_TITLES[level]}: ${RISK_DESCRIPTIONS[level]}` : `${RISK_TITLES[level]} (kilitli)`}
              />
              <span className="risk-option-body" aria-hidden="true">
                <span className="risk-option-title">
                  {allowed ? null : <LockIcon />}
                  {RISK_TITLES[level]}
                </span>
                <span className="risk-option-text">{allowed ? RISK_DESCRIPTIONS[level] : "Kilitli"}</span>
              </span>
            </label>
          );
        })}
      </div>
      <p id={noteId} className="field-hint">
        {note ?? ceilingNote(ceiling)}
      </p>
      {reasons.length > 0 ? (
        <ul className="risk-reasons text-sm">
          {reasons.map((reason) => (
            <li key={reason}>{reason}</li>
          ))}
        </ul>
      ) : null}
    </fieldset>
  );
}
