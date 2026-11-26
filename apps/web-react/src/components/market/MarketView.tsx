import type { ReactNode } from "react";
import type {
  MarketBacktest,
  MarketGroup,
  MarketKind,
  MarketMissed,
  MarketOverview,
  MarketPerformance,
  MarketPlan,
  MarketTrade,
  MarketViewItem,
} from "../../types/market";
import Badge from "../Badge";
import Card from "../Card";
import EmptyState from "../EmptyState";
import { BalanceChart } from "./charts";
import { ScoreBars, Stat } from "./parts";
import { KIND, KINDS, TEXT, assetName, date, day, kindName, percent, plain, price, rule, signed, signedUsd, usd, zone } from "./text";

// The 4.4 screens, ported from Aykut's src/portfolio/MarketPage.tsx. Presentational only: the page loads the data.

export type MarketTab = "overview" | "trades" | "missed" | "stats" | "backtest";
export type OpenTrade = (id: string) => void;

export function AccountStats({ account }: { account: MarketOverview["account"] }) {
  if (!account) return null;
  return (
    <div className="market-stats">
      <Stat
        label="Sanal kasa"
        value={usd(account.equity)}
        tone={account.percent < 0 ? "bad" : account.percent > 0 ? "good" : undefined}
        hint={`${signed(account.percent)} % · ${usd(account.startBalance, 0)} ile başladı`}
      />
      <Stat
        label="Başarılı / başarısız"
        value={`${account.won} / ${account.lost}`}
        hint={account.closedTrades ? `başarı ${percent((100 * account.won) / account.closedTrades, 1)}` : "kapanan işlem yok"}
      />
      <Stat
        label="Açık işlem"
        value={account.openTrades}
        hint={account.openTrades ? `açık sonuç ${signedUsd(account.openPnlUsd)}` : "şu an yok"}
      />
      <Stat label="Kaçırılan" value={account.missed} hint="motor kapalıyken oluşan" />
    </div>
  );
}

export function Overview({ data, plan, onOpen }: { data: MarketOverview; plan: MarketPlan | null; onOpen: OpenTrade }) {
  const opened = data.trades.filter((t) => t.status !== "CLOSED");
  return (
    <div className="stack-lg">
      <Card title="Açık sanal işlemler">
        <TradeTable
          trades={opened}
          onOpen={onOpen}
          emptyTitle={data.trades.length ? "Açık işlem yok" : TEXT.noPlanTitle}
          emptyText={data.trades.length ? TEXT.noOpenText : TEXT.noPlanText}
        />
      </Card>
      {plan && plan.items.length ? <PlanSizes plan={plan} /> : null}
      {data.view.length ? (
        <div className="grid grid-3">
          {data.view.map((v) => (
            <AssetCard key={v.asset} v={v} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

// the open trades sized for this user's IQ score
function PlanSizes({ plan }: { plan: MarketPlan }) {
  return (
    <Card title="Senin büyüklüğün" subtitle={`Açık işlemler Finansal IQ skoruna (${plan.iqScore}) göre boyutlandı.`}>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr>
              <th>Varlık</th>
              <th>Yön</th>
              <th>Tür</th>
              <th className="num">Teminat</th>
              <th className="num">Kaldıraç</th>
              <th className="num">Pozisyon</th>
              <th className="num">Risk</th>
            </tr>
          </thead>
          <tbody>
            {plan.items.map((t) => (
              <tr key={t.id}>
                <td>{assetName(t.asset)}</td>
                <td>{t.direction}</td>
                <td>{kindName(t.kind)}</td>
                <td className="num">kasanın {percent(t.size.marginPercent, 1)}</td>
                <td className="num">{t.size.leverage}x</td>
                <td className="num">{percent(t.size.notionalPercent, 1)}</td>
                <td className="num">{percent(t.size.riskPercent, 2)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

export function AssetCard({ v }: { v: MarketViewItem }) {
  const trigger = v.scan?.triggers[0] ?? null;
  const weights = Object.entries(v.weights ?? {});
  const top = Math.max(1, ...weights.map(([, w]) => w));
  return (
    <Card
      as="article"
      headingLevel={3}
      title={assetName(v.asset)}
      subtitle={v.scannedAt ? `Son tarama ${date(v.scannedAt)}` : v.asset === "BTC" ? "Henüz taranmadı (motor kapalı)." : "Canlı kaynak yok; yalnız geçmiş test."}
    >
      <div className="stack-sm">
        {v.scan?.problem ? <p className="text-secondary text-sm">Veri sorunu: {v.scan.problem}</p> : null}
        {trigger ? (
          <>
            <div className="cluster">
              <Badge tone="info">
                {trigger.direction} · {trigger.triggerFrame} uyumsuzluk
              </Badge>
              <Badge tone={trigger.kind ? "good" : "neutral"}>{trigger.kind ? KIND[trigger.kind] : "puan yetmedi"}</Badge>
            </div>
            <ScoreBars categories={trigger.categories} total={trigger.score} />
            {trigger.noPlan ? <p className="text-secondary text-sm">İşlem açılmadı: giriş yeri ya da hedef uygun değil.</p> : null}
          </>
        ) : v.scan ? (
          <p className="text-sm">Şu an uyumsuzluk yok; motor bekliyor.</p>
        ) : null}
        {v.limits ? (
          <>
            <h4 className="market-h4">Gereken puan</h4>
            <Limits limits={v.limits} value={trigger?.score ?? null} />
          </>
        ) : null}
        {weights.length ? (
          <details className="market-details">
            <summary>Kategori puanları</summary>
            <div className="market-bars">
              {weights.map(([name, w]) => (
                <div key={name}>
                  <span>{name}</span>
                  <i>
                    <b style={{ width: `${(100 * w) / top}%` }} />
                  </i>
                  <em>{plain(w)}</em>
                </div>
              ))}
            </div>
          </details>
        ) : null}
      </div>
    </Card>
  );
}

function Limits({ limits, value }: { limits: Record<MarketKind, number>; value: number | null }) {
  return (
    <div className="market-limits">
      <div className="market-limit-bar">
        {value !== null ? <b style={{ width: `${Math.min(100, value)}%` }} /> : null}
        {KINDS.map((k) => (
          <i key={k} style={{ left: `${limits[k]}%` }} />
        ))}
      </div>
      <dl>
        {KINDS.map((k) => (
          <div key={k}>
            <dt>{KIND[k]}</dt>
            <dd>{plain(limits[k])}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

export function TradeTable({
  trades,
  onOpen,
  emptyTitle = TEXT.noPlanTitle,
  emptyText = TEXT.noPlanText,
}: {
  trades: MarketTrade[];
  onOpen: OpenTrade;
  emptyTitle?: string;
  emptyText?: ReactNode;
}) {
  if (!trades.length) return <EmptyState title={emptyTitle} description={emptyText} />;
  return (
    <div className="table-wrap market-tall">
      <table className="table market-clickable">
        <thead>
          <tr>
            <th>Açılış (TSİ)</th>
            <th>Varlık</th>
            <th>Yön</th>
            <th>Tür</th>
            <th className="num">Giriş</th>
            <th className="num">Kaldıraç</th>
            <th className="num">Puan</th>
            <th>Durum</th>
            <th className="num">En iyi</th>
            <th className="num">Sonuç</th>
            <th className="num">R</th>
            <th className="num">Kasa</th>
            <th>Kâr alınan</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => {
            const result = t.pnlUsd + t.openPnlUsd;
            return (
              <tr
                key={t.id}
                tabIndex={0}
                aria-label={`${assetName(t.asset)} ${t.direction} ${t.openedAtTsi}: ayrıntı`}
                onClick={() => onOpen(t.id)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") onOpen(t.id);
                }}
              >
                <td>{t.openedAtTsi}</td>
                <td>{assetName(t.asset)}</td>
                <td>
                  <Badge tone={t.direction === "LONG" ? "good" : "critical"}>{t.direction}</Badge>
                </td>
                <td>{kindName(t.kind)}</td>
                <td className="num">{price(t.entry)}</td>
                <td className="num">{t.leverage}x</td>
                <td className="num">{plain(t.score)}</td>
                <td>
                  {t.status === "CLOSED"
                    ? zone(t.exitReason ?? "")
                    : t.status === "PARTIAL"
                      ? `Açık, ${percent(t.unitsLeft)} kaldı`
                      : "Açık"}
                </td>
                <td className="num">{percent(t.maxProfit.roiPercent)}</td>
                <td className={`num ${result > 0 ? "market-text-good" : result < 0 ? "market-text-bad" : ""}`}>{signedUsd(result)}</td>
                <td className="num">{t.resultR === null ? "–" : signed(t.resultR)}</td>
                <td className="num">{t.balanceAfter === null ? "–" : usd(t.balanceAfter)}</td>
                <td>{t.takeProfits.length ? t.takeProfits.map((f) => zone(f.zone)).join(", ") : "–"}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export function MissedList({ items }: { items: MarketMissed[] }) {
  return (
    <Card
      title="Kaçırılan işlemler"
      subtitle="Motor kapalıyken bütün koşullar sağlandı ama işlem açılmadı. Kasaya yansımaz; açılsaydı ne olurdu diye izlenir."
    >
      {!items.length ? (
        <EmptyState title={TEXT.noMissedTitle} description={TEXT.noMissedText} />
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Zaman (TSİ)</th>
                <th>Varlık</th>
                <th>Yön</th>
                <th>Tür</th>
                <th className="num">Giriş</th>
                <th className="num">Stop</th>
                <th className="num">Kaldıraç</th>
                <th className="num">Puan</th>
                <th>Onaylar</th>
                <th>Açılsaydı</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id}>
                  <td>{m.atTsi}</td>
                  <td>{assetName(m.asset)}</td>
                  <td>{m.direction}</td>
                  <td>{kindName(m.kind)}</td>
                  <td className="num">{price(m.entry)}</td>
                  <td className="num">{price(m.stop)}</td>
                  <td className="num">{m.leverage}x</td>
                  <td className="num">{plain(m.score)}</td>
                  <td>
                    {Object.entries(m.categories)
                      .map(([c, v]) => `${c} ${v.frame}`)
                      .join(", ")}
                  </td>
                  <td>
                    {m.wouldBe.status === "CLOSED"
                      ? `${zone(m.wouldBe.exitReason ?? "")}, ${signed(m.wouldBe.resultR ?? 0)} R`
                      : `sürüyor, teminata göre ${percent(m.wouldBe.roiPercent, 1)}`}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

export function StatsView({ p }: { p: MarketPerformance | null }) {
  if (!p || !p.n)
    return (
      <Card title="İstatistik">
        <EmptyState title={TEXT.noStatsTitle} description={TEXT.noStatsText} />
      </Card>
    );
  return (
    <div className="stack-lg">
      <div className="market-stats">
        <Stat label="Başarı oranı" value={percent(100 * (p.winRate ?? 0), 1)} hint={`${p.won} başarılı, ${p.lost} başarısız`} />
        <Stat label="İşlem başı ortalama" value={`${signed(p.averageR ?? 0)} R`} />
        <Stat label="Kâr faktörü" value={p.profitFactor === null ? "–" : plain(p.profitFactor, 2)} />
        <Stat label="En uzun kayıp serisi" value={p.longestLosingStreak ?? 0} />
      </div>
      <div className="grid grid-2">
        <Groups title="Hangi onay nasıl gitti" groups={p.byRule} name={rule} />
        <Groups title="Nasıl kapandı" groups={p.byExit} name={zone} />
      </div>
      <Groups title="Türe göre" groups={p.byKind} name={kindName} />
    </div>
  );
}

function Groups({ title, groups, name }: { title: string; groups: Record<string, MarketGroup>; name: (key: string) => string }) {
  const rows = Object.entries(groups ?? {});
  return (
    <Card title={title}>
      {!rows.length ? (
        <p className="text-secondary text-sm">Kayıt yok.</p>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th />
                <th className="num">İşlem</th>
                <th className="num">Başarılı</th>
                <th className="num">Başarısız</th>
                <th className="num">Ortalama R</th>
              </tr>
            </thead>
            <tbody>
              {rows.map(([k, g]) => (
                <tr key={k}>
                  <td>{name(k)}</td>
                  <td className="num">{g.n}</td>
                  <td className="num">{g.won}</td>
                  <td className="num">{g.lost}</td>
                  <td className={`num ${g.averageR > 0 ? "market-text-good" : "market-text-bad"}`}>{signed(g.averageR)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

const BACKTEST_ORDER = ["BTC", "GOLD", "SPX", "ALL"];

// the last year replayed with the live rules, next to the same run with shuffled entries
export function BacktestView({ backtest, onOpen }: { backtest: MarketBacktest | null; onOpen: OpenTrade }) {
  if (!backtest)
    return (
      <Card title="Geçen yılın testi">
        <EmptyState title={TEXT.noBacktestTitle} description={TEXT.noBacktestText} />
      </Card>
    );
  const assets = [
    ...BACKTEST_ORDER.filter((a) => backtest.real[a]),
    ...Object.keys(backtest.real).filter((a) => !BACKTEST_ORDER.includes(a)),
  ];
  const until = Math.max(0, ...Object.values(backtest.to ?? {}));
  const common = backtest.real.ALL?.account;
  return (
    <div className="stack-lg">
      <Card
        title="Geçen yılın testi"
        subtitle={`Aynı kurallar ${day(backtest.from)}${until ? ` – ${day(until)}` : ""} arasında yeniden oynatıldı. Karşılaştırma: aynı koşullarda rastgele girişler.`}
      >
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>Varlık</th>
                <th className="num">İşlem</th>
                <th className="num">Başarı</th>
                <th className="num">Ortalama R</th>
                <th className="num">Kâr faktörü</th>
                <th className="num">Kasa</th>
                <th className="num">En derin düşüş</th>
                <th className="num">Rastgele giriş</th>
              </tr>
            </thead>
            <tbody>
              {assets.map((a) => {
                const r = backtest.real[a];
                const c = backtest.control?.[a];
                return (
                  <tr key={a}>
                    <td>{assetName(a)}</td>
                    <td className="num">{r.all.n}</td>
                    <td className="num">{r.all.winRate === undefined ? "–" : percent(100 * r.all.winRate, 1)}</td>
                    <td className="num">{r.all.averageR === undefined ? "–" : signed(r.all.averageR)}</td>
                    <td className="num">{r.all.profitFactor === undefined || r.all.profitFactor === null ? "–" : plain(r.all.profitFactor, 2)}</td>
                    <td className={`num ${r.account.percent > 0 ? "market-text-good" : r.account.percent < 0 ? "market-text-bad" : ""}`}>
                      {signed(r.account.percent, 1)} %
                    </td>
                    <td className="num">{r.account.maxDrawdownPercent === undefined ? "–" : percent(r.account.maxDrawdownPercent, 1)}</td>
                    <td className="num">{c ? `${signed(c.account.percent, 1)} %` : "–"}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {common ? <BalanceChart points={backtest.curve} start={common.start} /> : null}
      </Card>
      <Card title="Testteki işlemler" subtitle="Üç varlık tek kasada. Satıra tıkla: plan, kâr bölgeleri, onaylar ve yorum.">
        <TradeTable trades={backtest.trades} onOpen={onOpen} emptyTitle="İşlem yok" emptyText="Bu testte işlem açılmadı." />
      </Card>
    </div>
  );
}
