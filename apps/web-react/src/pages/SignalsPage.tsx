import { useCallback } from "react";
import { getSignalPlans } from "../api/signalsApi";
import { useAuth } from "../auth/useAuth";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import ErrorBox from "../components/ErrorBox";
import PageHeader from "../components/PageHeader";
import Spinner from "../components/Spinner";
import PlanCard from "../components/signals/PlanCard";
import WatchlistSection from "../components/signals/WatchlistSection";
import { sortPlans } from "../components/signals/signalLabels";
import { useWatchlist } from "../components/signals/useWatchlist";
import { isWatched } from "../components/signals/watchlist";
import { useAsync } from "../lib/useAsync";
import type { SignalPlan } from "../types/signals";
import "../components/signals/signals.css";

// 4.4 "AInvest önerisi": rule-based market view and conditional plans for BTC, gold and the S&P 500. Sample data
// until the Portfolio Service's 4.4 module has an API (signalsApi). Plans are followed virtually; no order is sent.
export default function SignalsPage() {
  const { session } = useAuth();
  const plans = useAsync(useCallback(() => getSignalPlans(), []));
  const watchlist = useWatchlist(session?.userId);
  const list = plans.data ? sortPlans(plans.data) : [];

  const toggleWatch = (plan: SignalPlan) => {
    if (isWatched(watchlist.items, plan.asset)) watchlist.remove(plan.asset);
    else watchlist.add(plan);
  };

  return (
    <div className="page">
      <PageHeader
        title="Piyasa (4.4)"
        documentTitle="Piyasa"
        description="Kural tabanlı piyasa görüşü ve koşullu planlar: fiyat bir bölgeye gelirse alt zaman diliminde onay aranır."
      />

      {plans.loading && plans.data === undefined ? (
        <Spinner layout="block" label="Planlar yükleniyor…" />
      ) : plans.error ? (
        <ErrorBox title="Planlar yüklenemedi" error={plans.error} onRetry={plans.reload} />
      ) : list.length === 0 ? (
        <Card>
          <EmptyState title="Şu an plan yok" description="4.4 modülü henüz bir piyasa görüşü üretmedi." />
        </Card>
      ) : (
        <section aria-label="Varlıklar">
          <div className="signals-grid">
            {list.map((plan) => (
              <PlanCard
                key={plan.asset}
                plan={plan}
                watched={isWatched(watchlist.items, plan.asset)}
                onToggleWatch={toggleWatch}
              />
            ))}
          </div>
        </section>
      )}

      <WatchlistSection items={watchlist.items} persistent={watchlist.persistent} onRemove={watchlist.remove} />
    </div>
  );
}
