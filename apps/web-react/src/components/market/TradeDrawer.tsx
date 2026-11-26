import { useCallback, useEffect, useState } from "react";
import { getMarketTrade, type TradeSource } from "../../api/marketApi";
import { useAsync } from "../../lib/useAsync";
import type { MarketTradeDetail } from "../../types/market";
import Badge from "../Badge";
import EmptyState from "../EmptyState";
import ErrorBox from "../ErrorBox";
import Spinner from "../Spinner";
import { PlanLine } from "./charts";
import { ScoreBars, Stat, Tabs } from "./parts";
import { FRAMES, assetName, kindName, percent, plain, price, rule, signed, signedUsd, usd, zone } from "./text";

// one virtual (or backtest) trade: plan, fills, why it was opened, the two analyses and every confirmation
export default function TradeDrawer({ id, source, onClose }: { id: string; source: TradeSource; onClose: () => void }) {
  const trade = useAsync(useCallback((signal: AbortSignal) => getMarketTrade(id, source, { signal }), [id, source]));

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);

  const t = trade.data;
  return (
    <div className="market-overlay" onClick={onClose}>
      <aside
        className="market-drawer"
        role="dialog"
        aria-modal="true"
        aria-label="İşlem ayrıntısı"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="cluster-between">
          <h2 className="market-drawer-title">
            {t ? `${assetName(t.asset)} ${t.direction}` : "İşlem"} {t ? <Badge tone="info">{kindName(t.kind)}</Badge> : null}
          </h2>
          <button type="button" className="market-close" onClick={onClose} aria-label="Kapat" autoFocus>
            ×
          </button>
        </div>
        {trade.loading && !t ? <Spinner layout="block" label="İşlem yükleniyor…" /> : null}
        <ErrorBox title="İşlem yüklenemedi" error={trade.error} onRetry={trade.reload} />
        {!trade.loading && !trade.error && t === null ? <EmptyState title="İşlem bulunamadı" /> : null}
        {t ? <TradeBody t={t} /> : null}
      </aside>
    </div>
  );
}

export function TradeBody({ t }: { t: MarketTradeDetail }) {
  const [voice, setVoice] = useState<"standard" | "trader">("standard");
  const analysis = t.analysis?.[voice];
  const confirmations = t.confirmations ?? {};
  const frames = FRAMES.filter((f) => confirmations[f]?.length);
  return (
    <div className="stack">
      <p className="text-secondary text-sm">
        Açılış {t.openedAtTsi} (TSİ){t.closedAtTsi ? ` · kapanış ${t.closedAtTsi}` : " · sürüyor"} · {plain(t.durationHours)} saat
      </p>
      <div className="market-stats">
        <Stat
          label="Sonuç"
          value={signedUsd(t.pnlUsd)}
          tone={t.pnlUsd > 0 ? "good" : t.pnlUsd < 0 ? "bad" : undefined}
          hint={t.resultR !== null ? `${signed(t.resultR)} R · teminata göre ${percent(t.roiPercent ?? 0)}` : "gerçekleşen kısım"}
        />
        <Stat label="En yüksek kazanç" value={percent(t.maxProfit.roiPercent)} hint={`fiyatta ${percent(t.maxProfit.percent, 2)}`} />
        <Stat label="Kaldıraç · teminat" value={`${t.leverage}x`} hint={`${usd(t.marginUsd)} teminat, ${usd(t.notionalUsd)} pozisyon`} />
        <Stat label="Kasa" value={t.balanceAfter !== null ? usd(t.balanceAfter) : "–"} hint={`önce ${usd(t.balanceBefore)}`} />
      </div>

      <h3 className="market-h3">Plan ve gerçekleşen</h3>
      <PlanLine trade={t} />
      <p className="text-secondary text-sm">
        Giriş {price(t.entry)} · stop {price(t.stop)} ({percent(t.stopPercent, 2)}) · dolu noktalar gerçekleşti
      </p>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Olay</th>
              <th className="num">Fiyat</th>
              <th className="num">Birim</th>
              <th>Zaman (TSİ)</th>
              <th className="num">Sonuç</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Açılış</td>
              <td className="num">{price(t.entry)}</td>
              <td className="num">100</td>
              <td>{t.openedAtTsi}</td>
              <td />
            </tr>
            {[...t.takeProfits, ...(t.stopped ? [t.stopped] : [])].map((f) => (
              <tr key={f.zone}>
                <td>{zone(f.zone)}</td>
                <td className="num">{price(f.price)}</td>
                <td className="num">{plain(f.units, 0)}</td>
                <td>{f.atTsi}</td>
                <td className={`num ${f.pnlUsd > 0 ? "market-text-good" : "market-text-bad"}`}>{signedUsd(f.pnlUsd)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="market-h3">Neden açıldı</h3>
      <ScoreBars categories={t.categories} total={t.score} />

      {t.analysis ? (
        <>
          <h3 className="market-h3">Yorum</h3>
          <Tabs
            label="Yorum türü"
            tabs={[
              { id: "standard", label: "Standart analiz" },
              { id: "trader", label: "Trader analizi" },
            ]}
            value={voice}
            onChange={setVoice}
          />
          <p className="market-answer">{analysis || "Bu işlem için yorum yok."}</p>
        </>
      ) : null}

      {frames.length ? (
        <>
          <h3 className="market-h3">Bulunan bütün onaylar</h3>
          <div className="market-confirm">
            {frames.map((f) => (
              <div key={f}>
                <b>{f}</b>
                <span>
                  {confirmations[f].map((c) => (
                    <Badge key={c}>
                      {c.split("|")[0]}: {rule(c)}
                    </Badge>
                  ))}
                </span>
              </div>
            ))}
          </div>
        </>
      ) : null}
    </div>
  );
}
