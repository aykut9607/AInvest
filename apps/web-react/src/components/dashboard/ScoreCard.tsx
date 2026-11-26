import { Link } from "react-router-dom";
import { formatDateTime } from "../../lib/format";
import { SEGMENT_MEANINGS } from "../../lib/labels";
import { ROUTES } from "../../lib/routes";
import Card from "../Card";
import SegmentBadge from "../SegmentBadge";
import type { DashboardResult } from "./dashboardData";
import ScoreRing from "./ScoreRing";

// the score itself: ring + hero number, segment with its range and meaning, when it was calculated
export default function ScoreCard({ result }: { result: DashboardResult }) {
  const version = result.factorBreakdown?.version;
  return (
    <Card title="Finansal IQ skorun" className="score-card">
      <div className="score-card-body">
        <ScoreRing score={result.score} segment={result.segment} />
        <div className="score-card-details">
          <SegmentBadge segment={result.segment} withRange size="lg" />
          <p>{SEGMENT_MEANINGS[result.segment]}</p>
          <p className="text-sm text-muted">
            {result.calculatedAt ? `Hesaplanma: ${formatDateTime(result.calculatedAt)}` : "Az önce hesaplandı"}
            {version ? ` · Skor kuralları ${version}` : ""}
          </p>
          <div>
            <Link className="btn btn-secondary btn-sm" to={ROUTES.profile}>
              Profili düzenle
            </Link>
          </div>
        </div>
      </div>
    </Card>
  );
}
