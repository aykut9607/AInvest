import { SEVERITY_LABELS } from "../lib/labels";
import type { Severity } from "../types/api";
import Badge, { type BadgeTone } from "./Badge";

const TONE: Record<Severity, BadgeTone> = { CRITICAL: "critical", WARNING: "warning", INFO: "info" };

// KRİTİK / UYARI / BİLGİ for the alerts of GET /ai/insights/warnings
export default function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge tone={TONE[severity] ?? "neutral"} dot>
      {SEVERITY_LABELS[severity] ?? severity}
    </Badge>
  );
}
