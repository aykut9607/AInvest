import { useCallback } from "react";
import { explainScore } from "../../api/aiApi";
import AiAnswer from "../AiAnswer";
import Button from "../Button";
import Card from "../Card";
import ErrorBox from "../ErrorBox";
import Spinner from "../Spinner";
import { MODEL_WAIT_LABEL, aiRateLimitMessage, type DashboardResult } from "./dashboardData";
import { useOnDemand, useRateLimitGate } from "./hooks";

// Coach: POST /ai/explain-financial-iq with the result exactly as received, only when the user asks.
// Give it key={result.key} so a new result starts without the old answer.
export default function CoachCard({ result }: { result: DashboardResult }) {
  const run = useCallback(
    (signal: AbortSignal) =>
      explainScore(
        { score: result.score, segment: result.segment, factorBreakdown: result.factorBreakdown ?? undefined },
        { signal }
      ),
    [result.score, result.segment, result.factorBreakdown]
  );
  const coach = useOnDemand(run);
  const gate = useRateLimitGate(coach.error);

  return (
    <Card title="Koç" subtitle="Yapay zekâ koçu skorunu ve faktörlerini açıklar; yalnızca sen istediğinde çalışır.">
      <div className="stack" aria-busy={coach.loading || undefined}>
        {!coach.data && !coach.loading ? (
          <p className="text-secondary">
            Skorunun neden böyle olduğunu ve önce neyi iyileştirebileceğini öğrenmek için koça sor. Rakamlar senin
            verinden hesaplanır; koç yalnızca anlatır.
          </p>
        ) : null}
        <div className="cluster">
          <Button variant="primary" onClick={coach.start} loading={coach.loading} loadingLabel="Açıklanıyor…" disabled={gate.blocked}>
            {coach.data ? "Yeniden açıkla" : "Skorumu açıkla"}
          </Button>
          {coach.loading ? <Spinner size="sm" label={MODEL_WAIT_LABEL} /> : null}
        </div>
        <ErrorBox error={coach.error} title="Açıklama alınamadı" rateLimitMessage={aiRateLimitMessage} onRateLimitDone={gate.onDone} />
        {coach.data ? (
          <div className={coach.loading ? "is-refreshing" : undefined}>
            <AiAnswer title="Koç" text={coach.data.explanation} meta={coach.data} />
          </div>
        ) : null}
      </div>
    </Card>
  );
}
