import { useCallback, useState } from "react";
import type { PortfolioApi } from "./api";
import { ScoreBars, TradeDrawer } from "./TradeDetail";
import { ASSET, KIND, date, percent, plain, price, problem, rule, signed, signedUsd, usd, zone } from "./text";
import type { Account, Group, Kind, Missed, Performance, Trade, ViewItem } from "./types";
import { Banner, Button, Card, Empty, Loading, Pill, Tabs, Tile } from "./ui";
import { useLoad } from "./useLoad";

const MARKET = "/api/portfolio/market";
const KINDS: Kind[] = ["SCALP", "SCALP_SWING", "SWING"];
type Tab = "overview" | "trades" | "missed" | "stats";

interface Live {
  account: Account;
  view: ViewItem[];
  trades: Trade[];
  missed: Missed[];
  performance: Performance;
}

export default function MarketPage({ api }: { api: PortfolioApi }) {
  const load = useCallback(async (): Promise<Live> => {
    const [account, view, trades, missed, performance] = await Promise.all([
      api.get<Account>(`${MARKET}/account`),
      api.get<{ items: ViewItem[] }>(`${MARKET}/view`),
      api.get<{ items: Trade[] }>(`${MARKET}/trades?limit=200`),
      api.get<{ items: Missed[] }>(`${MARKET}/missed`),
      api.get<Performance>(`${MARKET}/performance`),
    ]);
    return { account, view: view.items, trades: trades.items, missed: missed.items, performance };
  }, [api]);
  const { data, error, loading, reload } = useLoad(load);
  const [tab, setTab] = useState<Tab>("overview");
  const [open, setOpen] = useState<string | null>(null);

  return (
    <>
      <header className="pf-head pf-row">
        <div>
          <h1>Piyasa (4.4)</h1>
          <p>Onay motorunun sanal işlemleri: hangi onaylarla açıldı, nerede kâr aldı, kasa ne oldu.</p>
        </div>
        <Button kind="quiet" onClick={reload} busy={loading && data !== null}>
          Yenile
        </Button>
      </header>
      <Banner kind="warning" title="Sanal işlem: gerçek emir gönderilmez">
        Yatırım tavsiyesi değildir. Yöntemin kazandırdığına dair yeterli kanıt yok; bu yüzden portföy önerisi olarak sunulmuyor.
      </Banner>
      {error !== null && (
        <Banner kind="danger" title="Yüklenemedi">
          {problem(error)}
        </Banner>
      )}
      {!data && loading && <Loading />}
      {data && (
        <>
          <div className="pf-tiles pf-tiles-big">
            <Tile label="Sanal kasa" value={usd(data.account.equity)} tone={data.account.percent < 0 ? "bad" : data.account.percent > 0 ? "good" : ""} hint={`${signed(data.account.percent)} % · ${usd(data.account.startBalance, 0)} ile başladı`} />
            <Tile label="Başarılı / başarısız" value={`${data.account.won} / ${data.account.lost}`} hint={data.account.closedTrades ? `başarı ${percent((100 * data.account.won) / data.account.closedTrades, 1)}` : "kapanan işlem yok"} />
            <Tile label="Açık işlem" value={data.account.openTrades} hint={data.account.openTrades ? `açık sonuç ${signedUsd(data.account.openPnlUsd)}` : "şu an yok"} />
            <Tile label="Kaçırılan" value={data.account.missed} hint="motor kapalıyken oluşan" />
          </div>
          <Tabs<Tab>
            tabs={[
              { id: "overview", label: "Genel bakış" },
              { id: "trades", label: "İşlemler", count: data.trades.length },
              { id: "missed", label: "Kaçırılanlar", count: data.missed.length },
              { id: "stats", label: "İstatistik" },
            ]}
            value={tab}
            onChange={setTab}
          />
          {tab === "overview" && <Overview live={data} onOpen={(id) => setOpen(`${MARKET}/trades/${id}`)} />}
          {tab === "trades" && (
            <Card title="Sanal işlem defteri" note="Her işlem güncel kasadan açılır (akümüle). Kayıtlar silinmez. Satıra tıkla: plan, kâr bölgeleri, onaylar ve yorum.">
              <TradeTable trades={data.trades} onOpen={(id) => setOpen(`${MARKET}/trades/${id}`)} empty="Motor açıkken oluşan ilk işlem burada görünecek." />
            </Card>
          )}
          {tab === "missed" && <MissedList items={data.missed} />}
          {tab === "stats" && <StatsView p={data.performance} />}
        </>
      )}
      {open && <TradeDrawer api={api} path={open} onClose={() => setOpen(null)} />}
    </>
  );
}

function Overview({ live, onOpen }: { live: Live; onOpen: (id: string) => void }) {
  const opened = live.trades.filter((t) => t.status !== "CLOSED");
  return (
    <>
      <Card title="Açık sanal işlemler">
        <TradeTable trades={opened} onOpen={onOpen} empty="Şu an açık işlem yok. Motor her 15 dakikada bir bakıyor." />
      </Card>
      <div className="pf-grid3">
        {live.view.map((v) => (
          <Asset key={v.asset} v={v} />
        ))}
      </div>
    </>
  );
}

function Asset({ v }: { v: ViewItem }) {
  const trigger = v.scan?.triggers[0] ?? null;
  return (
    <Card title={ASSET[v.asset] ?? v.asset} note={v.scannedAt ? `Son tarama ${date(v.scannedAt)}` : v.asset === "BTC" ? "Henüz taranmadı (motor kapalı)." : "Canlı kaynak yok; yalnız geçmiş test."}>
      {v.scan?.problem && <p className="pf-note">Veri sorunu: {v.scan.problem}</p>}
      {trigger ? (
        <>
          <div className="pf-row-start">
            <Pill tone="blue">
              {trigger.direction} · {trigger.triggerFrame} uyumsuzluk
            </Pill>
            <Pill tone={trigger.kind ? "good" : "neutral"}>{trigger.kind ? KIND[trigger.kind] : "puan yetmedi"}</Pill>
          </div>
          <ScoreBars categories={trigger.categories} total={trigger.score} />
          {trigger.noPlan && <p className="pf-note">İşlem açılmadı: giriş yeri ya da hedef uygun değil.</p>}
        </>
      ) : (
        v.scan && <p>Şu an uyumsuzluk yok; motor bekliyor.</p>
      )}
      <h3>Gereken puan</h3>
      <Limits limits={v.limits} value={trigger?.score ?? null} />
      <details>
        <summary>Kategori puanları</summary>
        <div className="pf-weights">
          {Object.entries(v.weights).map(([name, w]) => (
            <div key={name}>
              <span>{name}</span>
              <i>
                <b style={{ width: `${(100 * w) / Math.max(...Object.values(v.weights))}%` }} />
              </i>
              <em>{plain(w)}</em>
            </div>
          ))}
        </div>
      </details>
    </Card>
  );
}

function Limits({ limits, value }: { limits: Record<Kind, number>; value: number | null }) {
  return (
    <div className="pf-limits">
      <div className="pf-limit-bar">
        {value !== null && <b style={{ width: `${value}%` }} />}
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

function TradeTable({ trades, onOpen, empty }: { trades: Trade[]; onOpen: (id: string) => void; empty: string }) {
  if (!trades.length) return <Empty title="Kayıt yok">{empty}</Empty>;
  return (
    <div className="pf-scroll pf-tall">
      <table className="pf-table pf-click">
        <thead>
          <tr>
            <th>Açılış (TSİ)</th>
            <th>Varlık</th>
            <th>Yön</th>
            <th>Tür</th>
            <th>Giriş</th>
            <th>Kaldıraç</th>
            <th>Puan</th>
            <th>Durum</th>
            <th>En iyi</th>
            <th>Sonuç</th>
            <th>R</th>
            <th>Kasa</th>
            <th>Kâr alınan</th>
          </tr>
        </thead>
        <tbody>
          {trades.map((t) => (
            <tr key={t.id} tabIndex={0} onClick={() => onOpen(t.id)} onKeyDown={(e) => e.key === "Enter" && onOpen(t.id)}>
              <td>{t.openedAtTsi}</td>
              <td>{ASSET[t.asset] ?? t.asset}</td>
              <td>
                <Pill tone={t.direction === "LONG" ? "good" : "bad"}>{t.direction}</Pill>
              </td>
              <td>{KIND[t.kind]}</td>
              <td>{price(t.entry)}</td>
              <td>{t.leverage}x</td>
              <td>{plain(t.score)}</td>
              <td>{t.status === "CLOSED" ? zone(t.exitReason ?? "") : t.status === "PARTIAL" ? `Açık, ${percent(t.unitsLeft)} kaldı` : "Açık"}</td>
              <td>{percent(t.maxProfit.roiPercent)}</td>
              <td className={t.pnlUsd + t.openPnlUsd > 0 ? "pf-text-good" : "pf-text-bad"}>{signedUsd(t.pnlUsd + t.openPnlUsd)}</td>
              <td>{t.resultR === null ? "–" : signed(t.resultR)}</td>
              <td>{t.balanceAfter === null ? "–" : usd(t.balanceAfter)}</td>
              <td>{t.takeProfits.length ? t.takeProfits.map((f) => zone(f.zone)).join(", ") : "–"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function MissedList({ items }: { items: Missed[] }) {
  return (
    <Card title="Kaçırılan işlemler" note="Motor kapalıyken bütün koşullar sağlandı ama işlem açılmadı. Kasaya yansımaz; açılsaydı ne olurdu diye izlenir.">
      {!items.length ? (
        <Empty title="Kaçırılan işlem yok">Motor kapalıyken uygun bir durum oluşursa açıldığında buraya yazılır.</Empty>
      ) : (
        <div className="pf-scroll">
          <table className="pf-table">
            <thead>
              <tr>
                <th>Zaman (TSİ)</th>
                <th>Varlık</th>
                <th>Yön</th>
                <th>Tür</th>
                <th>Giriş</th>
                <th>Stop</th>
                <th>Kaldıraç</th>
                <th>Puan</th>
                <th>Onaylar</th>
                <th>Açılsaydı</th>
              </tr>
            </thead>
            <tbody>
              {items.map((m) => (
                <tr key={m.id}>
                  <td>{m.atTsi}</td>
                  <td>{ASSET[m.asset] ?? m.asset}</td>
                  <td>{m.direction}</td>
                  <td>{KIND[m.kind]}</td>
                  <td>{price(m.entry)}</td>
                  <td>{price(m.stop)}</td>
                  <td>{m.leverage}x</td>
                  <td>{plain(m.score)}</td>
                  <td>{Object.entries(m.categories).map(([c, v]) => `${c} ${v.frame}`).join(", ")}</td>
                  <td>
                    {m.wouldBe.status === "CLOSED" ? `${zone(m.wouldBe.exitReason ?? "")}, ${signed(m.wouldBe.resultR ?? 0)} R` : `sürüyor, teminata göre ${percent(m.wouldBe.roiPercent, 1)}`}
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

function StatsView({ p }: { p: Performance }) {
  if (!p.n)
    return (
      <Card title="İstatistik">
        <Empty title="Henüz kapanan işlem yok">İlk işlem kapanınca başarı oranı, çıkış türleri ve hangi onayın nasıl gittiği burada görünür.</Empty>
      </Card>
    );
  return (
    <>
      <div className="pf-tiles">
        <Tile label="Başarı oranı" value={percent(100 * (p.winRate ?? 0), 1)} hint={`${p.won} başarılı, ${p.lost} başarısız`} />
        <Tile label="İşlem başı ortalama" value={`${signed(p.averageR ?? 0)} R`} />
        <Tile label="Kâr faktörü" value={p.profitFactor === null ? "–" : plain(p.profitFactor, 2)} />
        <Tile label="En uzun kayıp serisi" value={p.longestLosingStreak ?? 0} />
      </div>
      <div className="pf-grid2">
        <Groups title="Hangi onay nasıl gitti" groups={p.byRule} name={rule} />
        <Groups title="Nasıl kapandı" groups={p.byExit} name={zone} />
      </div>
      <Groups title="Türe göre" groups={p.byKind} name={(k) => KIND[k as Kind] ?? k} />
    </>
  );
}

function Groups({ title, groups, name }: { title: string; groups: Record<string, Group>; name: (key: string) => string }) {
  return (
    <Card title={title}>
      <table className="pf-table">
        <thead>
          <tr>
            <th />
            <th>İşlem</th>
            <th>Başarılı</th>
            <th>Başarısız</th>
            <th>Ortalama R</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(groups).map(([k, g]) => (
            <tr key={k}>
              <td>{name(k)}</td>
              <td>{g.n}</td>
              <td>{g.won}</td>
              <td>{g.lost}</td>
              <td className={g.averageR > 0 ? "pf-text-good" : "pf-text-bad"}>{signed(g.averageR)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </Card>
  );
}
