import { useCallback, useState } from "react";
import { getMarketBacktest, getMarketOverview, getMarketPlan, type TradeSource } from "../api/marketApi";
import Button from "../components/Button";
import ErrorBox from "../components/ErrorBox";
import PageHeader from "../components/PageHeader";
import Spinner from "../components/Spinner";
import { AccountStats, BacktestView, MissedList, Overview, StatsView, TradeTable, type MarketTab } from "../components/market/MarketView";
import TradeDrawer from "../components/market/TradeDrawer";
import Card from "../components/Card";
import { Tabs } from "../components/market/parts";
import { TEXT } from "../components/market/text";
import { useAsync } from "../lib/useAsync";
import "../components/market/market.css";

// 4.4 "AInvest önerisi": the Portfolio Service's rule-based engine and its virtual trades (no order is ever sent).
export default function SignalsPage() {
  const overview = useAsync(useCallback((signal: AbortSignal) => getMarketOverview({ signal }), []));
  // the per-user sizing is optional: without an IQ result the page still shows the shared view
  const plan = useAsync(useCallback((signal: AbortSignal) => getMarketPlan({ signal }).catch(() => null), []));
  const [tab, setTab] = useState<MarketTab>("overview");
  const [open, setOpen] = useState<{ id: string; source: TradeSource } | null>(null);
  const data = overview.data;

  return (
    <div className="page">
      <PageHeader
        title="Piyasa (4.4)"
        documentTitle="Piyasa"
        description={TEXT.description}
        actions={
          <Button size="sm" onClick={overview.reload} loading={overview.loading && data !== undefined}>
            {TEXT.refresh}
          </Button>
        }
      />

      {overview.loading && data === undefined ? <Spinner layout="block" label={TEXT.loading} /> : null}
      <ErrorBox title={TEXT.loadError} error={overview.error} onRetry={overview.reload} />

      {data ? (
        <div className="stack-lg">
          <AccountStats account={data.account} />
          <Tabs<MarketTab>
            label="4.4 bölümleri"
            tabs={[
              { id: "overview", label: "Genel bakış" },
              { id: "trades", label: "İşlemler", count: data.trades.length },
              { id: "missed", label: "Kaçırılanlar", count: data.missed.length },
              { id: "stats", label: "İstatistik" },
              { id: "backtest", label: "Geçen yılın testi" },
            ]}
            value={tab}
            onChange={setTab}
          />
          {tab === "overview" ? (
            <Overview data={data} plan={plan.data ?? null} onOpen={(id) => setOpen({ id, source: "live" })} />
          ) : null}
          {tab === "trades" ? (
            <Card title="Sanal işlem defteri" subtitle="Her işlem güncel kasadan açılır. Satıra tıkla: plan, kâr bölgeleri, onaylar ve yorum.">
              <TradeTable trades={data.trades} onOpen={(id) => setOpen({ id, source: "live" })} />
            </Card>
          ) : null}
          {tab === "missed" ? <MissedList items={data.missed} /> : null}
          {tab === "stats" ? <StatsView p={data.performance} /> : null}
          {tab === "backtest" ? <BacktestTab onOpen={(id) => setOpen({ id, source: "backtest" })} /> : null}
        </div>
      ) : null}

      {open ? <TradeDrawer id={open.id} source={open.source} onClose={() => setOpen(null)} /> : null}
    </div>
  );
}

function BacktestTab({ onOpen }: { onOpen: (id: string) => void }) {
  const backtest = useAsync(useCallback((signal: AbortSignal) => getMarketBacktest({ signal }), []));
  if (backtest.loading && backtest.data === undefined) return <Spinner layout="block" label="Geçmiş test yükleniyor…" />;
  if (backtest.error) return <ErrorBox title="Geçmiş test yüklenemedi" error={backtest.error} onRetry={backtest.reload} />;
  return <BacktestView backtest={backtest.data ?? null} onOpen={onOpen} />;
}
