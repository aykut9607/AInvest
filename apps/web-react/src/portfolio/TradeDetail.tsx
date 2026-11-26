import { useCallback, useEffect, useState } from "react";
import type { PortfolioApi } from "./api";
import { PlanLine } from "./charts";
import { ASSET, FRAMES, KIND, percent, plain, price, problem, rule, signed, signedUsd, usd, zone } from "./text";
import type { Category, TradeDetail as Detail } from "./types";
import { Banner, Loading, Pill, Tabs, Tile } from "./ui";
import { useLoad } from "./useLoad";

export function ScoreBars({ categories, total }: { categories: Record<string, Category>; total: number }) {
  return (
    <div className="pf-score">
      {Object.entries(categories).map(([name, c]) => (
        <div key={name}>
          <span>
            {name}
            <small>
              {rule(c.rule)} · {c.frame}
              {c.also?.length ? ` · ${c.also.join(", ")} de destekliyor` : ""}
            </small>
          </span>
          <i>
            <b style={{ width: `${Math.min(100, (c.points / Math.max(total, 1)) * 100)}%` }} />
          </i>
          <em>{plain(c.points)}</em>
        </div>
      ))}
      <div className="pf-score-total">
        <span>Toplam puan</span>
        <i />
        <em>{plain(total)}</em>
      </div>
    </div>
  );
}

export function TradeDrawer({ api, path, onClose }: { api: PortfolioApi; path: string; onClose: () => void }) {
  const load = useCallback(() => api.get<Detail>(path), [api, path]);
  const { data: t, error, loading } = useLoad(load);
  const [voice, setVoice] = useState<"standard" | "trader">("standard");

  useEffect(() => {
    const key = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", key);
    return () => window.removeEventListener("keydown", key);
  }, [onClose]);

  return (
    <div className="pf-overlay" onClick={onClose}>
      <aside className="pf-drawer" role="dialog" aria-modal="true" aria-label="İşlem ayrıntısı" onClick={(e) => e.stopPropagation()}>
        <div className="pf-row">
          <h2>
            {t ? `${ASSET[t.asset] ?? t.asset} ${t.direction}` : "İşlem"} {t && <Pill>{KIND[t.kind]}</Pill>}
          </h2>
          <button type="button" className="pf-close" onClick={onClose} aria-label="Kapat" autoFocus>
            ×
          </button>
        </div>
        {loading && <Loading />}
        {error !== null && (
          <Banner kind="danger" title="Yüklenemedi">
            {problem(error)}
          </Banner>
        )}
        {t && (
          <>
            <p className="pf-note">
              Açılış {t.openedAtTsi} (TSİ){t.closedAtTsi ? ` · kapanış ${t.closedAtTsi}` : " · sürüyor"} · {plain(t.durationHours)} saat
            </p>
            <div className="pf-tiles">
              <Tile label="Sonuç" value={signedUsd(t.pnlUsd)} tone={t.pnlUsd > 0 ? "good" : "bad"} hint={t.resultR !== null ? `${signed(t.resultR)} R · teminata göre ${percent(t.roiPercent ?? 0)}` : "gerçekleşen kısım"} />
              <Tile label="En yüksek kazanç" value={percent(t.maxProfit.roiPercent)} hint={`fiyatta ${percent(t.maxProfit.percent, 2)}`} />
              <Tile label="Kaldıraç · teminat" value={`${t.leverage}x`} hint={`${usd(t.marginUsd)} teminat, ${usd(t.notionalUsd)} pozisyon`} />
              <Tile label="Kasa" value={t.balanceAfter !== null ? usd(t.balanceAfter) : "–"} hint={`önce ${usd(t.balanceBefore)}`} />
            </div>

            <h3>Plan ve gerçekleşen</h3>
            <PlanLine trade={t} />
            <p className="pf-note">
              Giriş {price(t.entry)} · stop {price(t.stop)} ({percent(t.stopPercent, 2)}) · dolu noktalar gerçekleşti
            </p>
            <p className="pf-note">
              Stop = girişten tepeye (dipte dibe) olan fark + SFP payı (BTC %2, altın ve S&P %0,5), en çok %5 (altın ve S&P %1,25). Kaldıraç = 100 / stop
              (%5 → 20x, %4 → 25x, %3 → 33x; swing en çok 10x): stopta teminat biter, kayıp hesabın %1'i. Teminat +%50 olunca yarısı kapanır, stop girişe çekilir.
            </p>
            <div className="pf-scroll">
              <table className="pf-table">
                <thead>
                  <tr>
                    <th>Olay</th>
                    <th>Fiyat</th>
                    <th>Birim</th>
                    <th>Zaman (TSİ)</th>
                    <th>Sonuç</th>
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>Açılış</td>
                    <td>{price(t.entry)}</td>
                    <td>100</td>
                    <td>{t.openedAtTsi}</td>
                    <td />
                  </tr>
                  {[...t.takeProfits, ...(t.stopped ? [t.stopped] : [])].map((f) => (
                    <tr key={f.zone}>
                      <td>{zone(f.zone)}</td>
                      <td>{price(f.price)}</td>
                      <td>{f.units}</td>
                      <td>{f.atTsi}</td>
                      <td className={f.pnlUsd > 0 ? "pf-text-good" : "pf-text-bad"}>{signedUsd(f.pnlUsd)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <h3>Neden açıldı</h3>
            <ScoreBars categories={t.categories} total={t.score} />

            <h3>Yorum</h3>
            <Tabs
              tabs={[
                { id: "standard", label: "Standart analiz" },
                { id: "trader", label: "Trader analizi" },
              ]}
              value={voice}
              onChange={setVoice}
            />
            <p className="pf-answer">{t.analysis[voice]}</p>

            <h3>Bulunan bütün onaylar</h3>
            <div className="pf-confirm">
              {FRAMES.filter((f) => t.confirmations[f]?.length).map((f) => (
                <div key={f}>
                  <b>{f}</b>
                  <span>
                    {t.confirmations[f].map((c) => (
                      <Pill key={c}>
                        {c.split("|")[0]}: {rule(c)}
                      </Pill>
                    ))}
                  </span>
                </div>
              ))}
            </div>
          </>
        )}
      </aside>
    </div>
  );
}
