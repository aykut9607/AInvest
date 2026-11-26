import { useEffect, useRef, useState } from "react";
import { explainPortfolio } from "../../api/aiApi";
import { isAbortError } from "../../api/http";
import type { PortfolioExplanationResponse } from "../../types/api";
import AiAnswer from "../AiAnswer";
import Badge from "../Badge";
import Button from "../Button";
import ErrorBox from "../ErrorBox";
import Notice from "../Notice";

// "Öneriyi açıkla": the Coach explains the proposal (GET /ai/explain-portfolio). The AI service reads the proposal
// itself (the sample while the Portfolio Service does not exist), so nothing is sent from here.
export default function ExplainPortfolio() {
  const [result, setResult] = useState<PortfolioExplanationResponse | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(false);
  const controller = useRef<AbortController | null>(null);

  useEffect(() => () => controller.current?.abort(), []);

  const run = async () => {
    controller.current?.abort();
    const current = new AbortController();
    controller.current = current;
    setLoading(true);
    setError(null);
    try {
      const response = await explainPortfolio({ signal: current.signal });
      if (!current.signal.aborted) setResult(response);
    } catch (err) {
      if (!current.signal.aborted && !isAbortError(err)) setError(err);
    } finally {
      if (!current.signal.aborted) setLoading(false);
    }
  };

  return (
    <div className="stack">
      <div className="cluster">
        <Button variant="primary" onClick={run} loading={loading} loadingLabel="Açıklanıyor…" disabled={loading}>
          {result ? "Yeniden açıkla" : "Öneriyi açıkla"}
        </Button>
        {loading ? (
          <span className="text-sm text-muted" role="status">
            Koç açıklıyor… yerel model 30–60 sn sürebilir.
          </span>
        ) : null}
      </div>

      <ErrorBox
        error={error}
        title="Açıklama alınamadı"
        onRetry={run}
        rateLimitMessage={(s) => `Dakikada en fazla 10 AI isteği gönderilebilir. ${s} saniye sonra tekrar dene.`}
        onRateLimitDone={() => setError(null)}
      />

      {result ? (
        <div className={`stack-sm${loading ? " is-refreshing" : ""}`}>
          {result.source === "sample" ? null : (
            <div className="cluster">
              <Badge tone="info">Portföy servisindeki önerin açıklandı</Badge>
            </div>
          )}
          {result.stale ? (
            <Notice tone="warning" title="Önerin eski bir skora dayanıyor">
              Öneri, son Finansal IQ'ndan önceki bir skorla hesaplandığı için açıklanmadı; aşağıda nedeni yazıyor.
            </Notice>
          ) : null}
          <AiAnswer text={result.explanation} meta={result} />
        </div>
      ) : null}
    </div>
  );
}
