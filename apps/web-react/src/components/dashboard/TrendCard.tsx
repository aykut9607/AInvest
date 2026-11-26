import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { explainTrend } from "../../api/aiApi";
import { getIqHistory } from "../../api/iqApi";
import { SEGMENT_LABELS } from "../../lib/labels";
import { ROUTES } from "../../lib/routes";
import { useAsync } from "../../lib/useAsync";
import type { IqTrendPoint } from "../../types/api";
import AiAnswer from "../AiAnswer";
import Button from "../Button";
import Card from "../Card";
import ErrorBox from "../ErrorBox";
import Spinner from "../Spinner";
import { MODEL_WAIT_LABEL, aiRateLimitMessage, trendRows } from "./dashboardData";
import { useOnDemand, useRateLimitGate } from "./hooks";
import TrendChart from "./TrendChart";

// the history call asks for this many calculations (the service allows 1-100)
const HISTORY_TAKE = 12;

export function TrendTable({ points }: { points: IqTrendPoint[] }) {
  return (
    <div className="table-wrap">
      <table className="table dash-table" data-testid="trend-table">
        <caption className="visually-hidden">Skor geçmişi, eskiden yeniye</caption>
        <thead>
          <tr>
            <th scope="col">Tarih</th>
            <th scope="col" className="num">
              Skor
            </th>
            <th scope="col">Segment</th>
            <th scope="col" className="num">
              Değişim
            </th>
            <th scope="col" className="num">
              3'lü ort.
            </th>
          </tr>
        </thead>
        <tbody>
          {trendRows(points).map((row) => (
            <tr key={row.key}>
              <td>{row.date}</td>
              <td className="num">{row.score}</td>
              <td>{SEGMENT_LABELS[row.segment] ?? row.segment}</td>
              <td className="num">{row.change}</td>
              <td className="num">{row.average}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// the chart, or a note when there is not enough history for a line yet
export function TrendView({ points, showTable }: { points: IqTrendPoint[]; showTable: boolean }) {
  if (points.length < 2) {
    return (
      <div className="stack-sm">
        <p>Trend için en az iki hesaplama gerekiyor.</p>
        <p className="text-sm text-secondary">
          {points.length === 1
            ? `Şu an bir hesaplaman var (skor ${points[0].score}). `
            : "Henüz kayıtlı bir hesaplaman yok. "}
          Profilini güncelleyip skorunu yeniden hesapladığında gelişimin burada çizilir.
        </p>
        <div>
          <Link className="btn btn-secondary btn-sm" to={ROUTES.profile}>
            Profili güncelle
          </Link>
        </div>
      </div>
    );
  }
  return showTable ? <TrendTable points={points} /> : <TrendChart points={points} />;
}

// GET /history (last 12 calculations) as a line chart with a table toggle; "Trendi açıkla" asks the Coach on demand
export default function TrendCard({ className }: { className?: string }) {
  const history = useAsync(useCallback((signal: AbortSignal) => getIqHistory(HISTORY_TAKE, { signal }), []));
  const [showTable, setShowTable] = useState(false);
  const explain = useOnDemand(useCallback((signal: AbortSignal) => explainTrend({ signal }), []));
  const gate = useRateLimitGate(explain.error);

  const points = history.data ?? [];
  const hasTrend = points.length >= 2;

  let body;
  if (history.data === undefined && history.loading) {
    body = <Spinner label="Skor geçmişi yükleniyor…" />;
  } else if (history.data === undefined && history.error) {
    body = <ErrorBox title="Skor geçmişi yüklenemedi" error={history.error} onRetry={history.reload} />;
  } else {
    body = (
      <div className="stack">
        <TrendView points={points} showTable={showTable} />
        {hasTrend ? (
          <div className="stack trend-explain">
            <div className="cluster">
              <Button onClick={explain.start} loading={explain.loading} loadingLabel="Açıklanıyor…" disabled={gate.blocked}>
                {explain.data ? "Trendi yeniden açıkla" : "Trendi açıkla"}
              </Button>
              {explain.loading ? <Spinner size="sm" label={MODEL_WAIT_LABEL} /> : null}
            </div>
            <ErrorBox
              error={explain.error}
              title="Trend açıklaması alınamadı"
              rateLimitMessage={aiRateLimitMessage}
              onRateLimitDone={gate.onDone}
            />
            {explain.data ? (
              <div className={explain.loading ? "is-refreshing" : undefined}>
                <AiAnswer title="Koç: skor geçmişin" text={explain.data.explanation} meta={explain.data} />
              </div>
            ) : null}
          </div>
        ) : null}
      </div>
    );
  }

  return (
    <Card
      title="Skor geçmişi"
      subtitle={`Son ${HISTORY_TAKE} hesaplamaya kadar, eskiden yeniye.`}
      className={className}
      actions={
        hasTrend ? (
          <Button size="sm" className="dash-toggle" aria-pressed={showTable} onClick={() => setShowTable((value) => !value)}>
            Tablo
          </Button>
        ) : null
      }
    >
      {body}
    </Card>
  );
}
