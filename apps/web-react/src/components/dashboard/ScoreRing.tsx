import { SEGMENT_LABELS } from "../../lib/labels";
import type { Segment } from "../../types/api";

const SIZE = 168;
const STROKE = 12;
const RADIUS = (SIZE - STROKE) / 2;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

// 0-100 ring in the segment's status colour on a sunken track; the number in the middle is the page's hero figure
export default function ScoreRing({ score, segment }: { score: number; segment: Segment }) {
  const clamped = Math.min(100, Math.max(0, score));
  const arc = (clamped / 100) * CIRCUMFERENCE;
  const centre = SIZE / 2;

  return (
    <div
      className="score-ring"
      data-segment={segment}
      role="img"
      aria-label={`Finansal IQ skoru ${score} / 100, segment ${SEGMENT_LABELS[segment] ?? segment}`}
    >
      <svg width={SIZE} height={SIZE} viewBox={`0 0 ${SIZE} ${SIZE}`} aria-hidden="true" focusable="false">
        <circle className="score-ring-track" cx={centre} cy={centre} r={RADIUS} strokeWidth={STROKE} fill="none" />
        {arc > 0 ? (
          <circle
            className="score-ring-arc"
            cx={centre}
            cy={centre}
            r={RADIUS}
            strokeWidth={STROKE}
            fill="none"
            strokeLinecap="round"
            strokeDasharray={`${arc} ${CIRCUMFERENCE}`}
            transform={`rotate(-90 ${centre} ${centre})`}
          />
        ) : null}
      </svg>
      <div className="score-ring-text" aria-hidden="true">
        <span className="score-ring-value" data-testid="score-value">
          {score}
        </span>
        <span className="score-ring-max">/ 100</span>
      </div>
    </div>
  );
}
