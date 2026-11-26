import { useCallback, useMemo } from "react";
import { Link, useLocation } from "react-router-dom";
import { getLatestIq } from "../api/iqApi";
import Card from "../components/Card";
import AppliedRuleCard from "../components/dashboard/AppliedRuleCard";
import CoachCard from "../components/dashboard/CoachCard";
import { currentResult, freshCalculation, type DashboardResult } from "../components/dashboard/dashboardData";
import DebtPayoffCard from "../components/dashboard/DebtPayoffCard";
import FactorBreakdownCard from "../components/dashboard/FactorBreakdownCard";
import ScoreCard from "../components/dashboard/ScoreCard";
import TrendCard from "../components/dashboard/TrendCard";
import WarningsCard from "../components/dashboard/WarningsCard";
import "../components/dashboard/dashboard.css";
import EmptyState from "../components/EmptyState";
import ErrorBox from "../components/ErrorBox";
import Notice from "../components/Notice";
import PageHeader from "../components/PageHeader";
import Spinner from "../components/Spinner";
import { ROUTES } from "../lib/routes";
import { useAsync } from "../lib/useAsync";

interface DashboardContentProps {
  result: DashboardResult;
  justCalculated: boolean;
  // /latest failed while the result from the navigation is on screen
  latestError: unknown;
}

// Only GET /ai/insights/warnings (rule-based, quick) runs by itself; the Coach and trend explanations wait for a click
// (the gateway allows 10 AI requests a minute per user and the local model may take a minute).
function DashboardContent({ result, justCalculated, latestError }: DashboardContentProps) {
  const rule = result.factorBreakdown?.appliedRule;
  return (
    <>
      {justCalculated ? (
        <Notice tone="good" title="Skorun güncellendi">
          Profilin kaydedildi ve Finansal IQ skorun yeniden hesaplandı.
        </Notice>
      ) : null}
      {latestError && !result.calculatedAt ? (
        <Notice tone="warning">Son kayıtlı sonuç alınamadı; az önce hesaplanan skorun gösteriliyor.</Notice>
      ) : null}
      <div className="dash-grid">
        <div className="stack">
          <ScoreCard result={result} />
          {rule ? <AppliedRuleCard rule={rule} /> : null}
        </div>
        <FactorBreakdownCard breakdown={result.factorBreakdown} score={result.score} />
        <WarningsCard breakdown={result.factorBreakdown} />
        <CoachCard key={result.key} result={result} />
        <TrendCard className="dash-span" />
        <DebtPayoffCard className="dash-span" />
      </div>
    </>
  );
}

// /panel: score, factor breakdown, warnings, Coach, score history and debt payoff. After "Kaydet ve hesapla" the
// profile page passes the fresh result in location.state, so it shows at once; /latest is still loaded.
export default function DashboardPage() {
  const location = useLocation();
  const fresh = useMemo(() => freshCalculation(location.state), [location.state]);
  const latest = useAsync(useCallback((signal: AbortSignal) => getLatestIq({ signal }), []));
  const result = useMemo(() => currentResult(fresh, latest.data), [fresh, latest.data]);

  let content;
  if (result) {
    content = <DashboardContent result={result} justCalculated={fresh !== undefined} latestError={latest.error} />;
  } else if (latest.loading) {
    content = <Spinner layout="block" label="Hazırlanıyor: Finansal IQ skorun yükleniyor…" />;
  } else if (latest.error) {
    content = <ErrorBox title="Skorun yüklenemedi" error={latest.error} onRetry={latest.reload} />;
  } else {
    content = (
      <Card>
        <EmptyState
          title="Henüz Finansal IQ skorun yok"
          description="Gelir, gider, borç ve birikim bilgilerini gir; skorun hesaplanınca faktör dökümü, uyarılar ve gelişimin burada görünür."
          action={
            <Link className="btn btn-primary" to={ROUTES.profile}>
              Önce finansal profilini gir
            </Link>
          }
        />
      </Card>
    );
  }

  return (
    <div className="page dashboard">
      <PageHeader title="Panel" description="Finansal IQ skorun, faktör dökümü, uyarılar ve skor geçmişin bir arada." />
      {content}
    </div>
  );
}
