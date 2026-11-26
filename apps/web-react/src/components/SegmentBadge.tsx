import { SEGMENT_LABELS, SEGMENT_RANGES } from "../lib/labels";
import type { Segment } from "../types/api";
import Badge, { type BadgeTone } from "./Badge";

const TONE: Record<Segment, BadgeTone> = { LOW: "critical", MEDIUM: "warning", HIGH: "good" };

export interface SegmentBadgeProps {
  segment: Segment;
  // adds the score range, e.g. "ORTA · 41–70"
  withRange?: boolean;
  size?: "md" | "lg";
}

export default function SegmentBadge({ segment, withRange = false, size = "md" }: SegmentBadgeProps) {
  const label = SEGMENT_LABELS[segment] ?? segment;
  return (
    <Badge tone={TONE[segment] ?? "neutral"} dot size={size} title={`Segment: ${label} (${SEGMENT_RANGES[segment] ?? ""})`}>
      {label}
      {withRange ? ` · ${SEGMENT_RANGES[segment]}` : ""}
    </Badge>
  );
}
