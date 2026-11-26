import { useCallback } from "react";
import { getWarnings } from "../../api/aiApi";
import { RateLimitError } from "../../api/http";
import { warningLabel } from "../../lib/labels";
import { useAsync } from "../../lib/useAsync";
import type { Alert, FactorBreakdown } from "../../types/api";
import Button from "../Button";
import Card from "../Card";
import ErrorBox from "../ErrorBox";
import SeverityBadge from "../SeverityBadge";
import Spinner from "../Spinner";
import { aiRateLimitMessage, sortAlerts } from "./dashboardData";
import { useRateLimitGate } from "./hooks";

function CalmState() {
  return (
    <div className="dash-calm" role="status">
      <svg className="dash-calm-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M8 12.5l2.5 2.5L16 9.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div>
        <p className="dash-calm-title">Önemli bir uyarı yok</p>
        <p className="text-sm text-secondary">Profilinde şu an dikkat gerektiren bir durum görünmüyor.</p>
      </div>
    </div>
  );
}

export function AlertList({ alerts }: { alerts: Alert[] }) {
  if (alerts.length === 0) return <CalmState />;
  return (
    <ul className="alert-list" data-testid="alert-list">
      {sortAlerts(alerts).map((alert, index) => (
        <li key={`${alert.code}-${index}`} className="alert-item" data-severity={alert.severity}>
          <SeverityBadge severity={alert.severity} />
          <p>{alert.message}</p>
        </li>
      ))}
    </ul>
  );
}

// the IQ breakdown's own warning list, used when the AI alerts cannot be loaded
function BasicWarnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return <CalmState />;
  return (
    <ul className="alert-list alert-list-basic">
      {warnings.map((warning) => (
        <li key={warning} className="alert-item">
          <span className="alert-bullet" aria-hidden="true" />
          <p>{warningLabel(warning)}</p>
        </li>
      ))}
    </ul>
  );
}

// GET /ai/insights/warnings (rule-based, no model) on load; falls back to the breakdown's warnings when it fails
export default function WarningsCard({ breakdown }: { breakdown: FactorBreakdown | null }) {
  const warnings = useAsync(useCallback((signal: AbortSignal) => getWarnings({ signal }), []));
  const gate = useRateLimitGate(warnings.error);
  const rateLimited = warnings.error instanceof RateLimitError;

  let body;
  if (warnings.data && !warnings.error) {
    body = (
      <div className="stack">
        <AlertList alerts={warnings.data.alerts} />
      </div>
    );
  } else if (warnings.loading) {
    body = <Spinner label="Uyarılar yükleniyor…" />;
  } else {
    body = (
      <div className="stack">
        <ErrorBox
          error={warnings.error}
          title="Ayrıntılı uyarılar alınamadı"
          onRetry={rateLimited ? undefined : warnings.reload}
          rateLimitMessage={aiRateLimitMessage}
          onRateLimitDone={gate.onDone}
        />
        {rateLimited && !gate.blocked ? (
          <div>
            <Button size="sm" onClick={warnings.reload}>
              Tekrar dene
            </Button>
          </div>
        ) : null}
        <p className="text-sm text-secondary">Skor dökümündeki temel uyarı listesi:</p>
        <BasicWarnings warnings={breakdown?.warnings ?? []} />
      </div>
    );
  }

  return (
    <Card title="Uyarılar" subtitle="Profiline göre dikkat etmen gerekenler, önem sırasıyla.">
      {body}
    </Card>
  );
}
