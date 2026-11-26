import { useCallback, useState } from "react";
import { ApiError, type PortfolioApi } from "./api";
import { Distribution } from "./charts";
import { LEVEL, OPTION, RISK_TEXT, SEGMENT, date, month, percent, problem, reason, tl } from "./text";
import type { Explanation, Investable, Level, Option, PortfolioOptions, Preferences, Proposal, Style } from "./types";
import { Banner, Button, Card, Chips, Choice, Empty, Loading, Pill, Tile } from "./ui";
import { useLoad } from "./useLoad";

const LEVELS: Level[] = ["LOW", "MEDIUM", "HIGH"];
const TONE: Record<Level, "good" | "warn" | "bad"> = { HIGH: "good", MEDIUM: "warn", LOW: "bad" };

interface Loaded {
  options: PortfolioOptions;
  saved: Preferences | null;
  latest: Proposal | null;
}

async function orNull<T>(request: Promise<T>): Promise<T | null> {
  try {
    return await request;
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) return null;
    throw error;
  }
}

// where the share and the two amounts come from, step by step (the numbers are the service's, nothing is computed here but the display)
function HowInvestable({ iq, i }: { iq: number; i: Investable }) {
  const b = i.basis;
  if (!b) return null;
  const share = i.sharePercent;
  const reserveFirst = i.reasons?.includes("RESERVE_FIRST");
  return (
    <details className="pf-how">
      <summary>Bu rakamlar nereden geliyor?</summary>
      <ol>
        <li>
          <b>Yatırılabilir pay</b> = Finansal IQ − 30 = {iq} − 30, en az %0 en çok %70 → <b>{percent(share)}</b>
          {reserveFirst && " (acil durum fonun eksik olduğu için önce onu tamamlaman gerekiyor; pay 0)"}.
        </li>
        <li>
          <b>Aylık artı</b> = gelir − gider − taksit = {tl(b.monthlyIncome)} − {tl(b.monthlyExpenses)} − {tl(b.monthlyDebtPayment)} = {tl(b.monthlySurplus)}.
          Bunun {percent(share)}'si → <b>her ay {tl(i.monthlyAmount)}</b>.
        </li>
        <li>
          <b>Acil durum fonu</b> = {b.reserveMonths} × aylık gider = {tl(b.emergencyFund)}. Nakdin {tl(b.cashReserve)}; fonun üstünde kalan {tl(b.freeCash)}.
          Bunun {percent(share)}'si → <b>tek seferlik {tl(i.oneTimeAmount)}</b>.
        </li>
        <li>
          Kalan kısım (aylık artının ve fazla nakdin %{100 - share}'si, acil durum fonu ve mevcut yatırımların) sende kalır; bu öneriye girmez.
          Acil fon kontrolünde nakit + yatırımların yarısı sayılır: {tl(b.reserve)}.
        </li>
      </ol>
    </details>
  );
}

export default function PortfolioPage({ api, marketOpen, onChosen, onOpenMarket, onOpenProfile }: { api: PortfolioApi; marketOpen: boolean; onChosen: () => void; onOpenMarket: () => void; onOpenProfile: () => void }) {
  const base = `/api/portfolio/${encodeURIComponent(api.userId)}`;
  const load = useCallback(async (): Promise<Loaded> => {
    const [options, saved, latest] = await Promise.all([api.get<PortfolioOptions>(`${base}/options`), orNull(api.get<Preferences>(`${base}/preferences`)), orNull(api.get<Proposal>(`${base}/latest`))]);
    return { options, saved, latest };
  }, [api, base]);
  const { data, error, loading, reload } = useLoad(load);

  return (
    <>
      <header className="pf-head">
        <h1>Portföy</h1>
        <p>Finansal IQ'nu gördükten sonra portföy türünü ve risk seviyeni seç; dağılımı Portföy servisi hesaplar, koç açıklar.</p>
      </header>
      {data ? (
        <Chooser key={data.options.iqScore} api={api} base={base} loaded={data} marketOpen={marketOpen} onChosen={onChosen} onOpenMarket={onOpenMarket} />
      ) : loading ? (
        <Loading />
      ) : error instanceof ApiError && error.status === 404 ? (
        <Card>
          <Empty title="Önce finansal profilini doldur">Portföy önerisi Finansal IQ skoruna dayanır. Profilini kaydedip skorunu hesapladıktan sonra burası açılır.</Empty>
          <div className="pf-center">
            <Button onClick={onOpenProfile}>Profilini doldur</Button>
          </div>
        </Card>
      ) : (
        <>
          <Banner kind="danger" title="Yüklenemedi">
            {problem(error)}
          </Banner>
          <Button kind="quiet" onClick={reload}>
            Yeniden dene
          </Button>
        </>
      )}
    </>
  );
}

function Chooser({ api, base, loaded, marketOpen, onChosen, onOpenMarket }: { api: PortfolioApi; base: string; loaded: Loaded; marketOpen: boolean; onChosen: () => void; onOpenMarket: () => void }) {
  const { options, saved } = loaded;
  const rank = LEVELS.indexOf(options.maxRisk);
  const usable = saved && saved.option !== "AINVEST" ? saved : null;
  const [option, setOption] = useState<Option | null>(usable?.option ?? null);
  const [risk, setRisk] = useState<Level | null>(usable && LEVELS.indexOf(usable.riskLevel) <= rank ? usable.riskLevel : null);
  const [style, setStyle] = useState<Style | null>(usable?.institutionStyle ?? null);
  const [focus, setFocus] = useState<string[]>(usable?.focusAssets ?? []);
  const [excluded, setExcluded] = useState<string[]>(usable?.excludedAssets ?? []);
  const [proposal, setProposal] = useState<Proposal | null>(loaded.latest);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<unknown>(null);

  const label = (code: string) => options.assetInfo.find((a) => a.code === code)?.label ?? code;
  const toggle = (list: string[], set: (v: string[]) => void) => (code: string) => set(list.includes(code) ? list.filter((x) => x !== code) : [...list, code]);

  const missing = [!option && "portföy türü", !risk && "risk seviyesi", option === "INSTITUTION" && !style && "kurum", option === "CUSTOM" && focus.length === 0 && "en az bir varlık"].filter(Boolean);

  // a field that does not belong to the option is refused by the service, so it is not sent
  const choice = (): Preferences | null => {
    if (!option || !risk || missing.length) return null;
    const excludedAssets = option !== "INSTITUTION" && excluded.length ? excluded : undefined;
    return { option, riskLevel: risk, ...(option === "INSTITUTION" ? { institutionStyle: style } : {}), ...(option === "CUSTOM" ? { focusAssets: focus } : {}), ...(excludedAssets ? { excludedAssets } : {}) };
  };

  const calculate = async () => {
    const body = choice();
    if (!body) return;
    setBusy(true);
    setFailed(null);
    try {
      await api.send("PUT", `${base}/preferences`, body);
      onChosen();          // the market (4.4) opens once a choice is saved, also when 4.4 itself is not ready yet
      setProposal(await api.send<Proposal>("POST", `${base}/proposal`));
      requestAnimationFrame(() => document.getElementById("pf-proposal")?.scrollIntoView({ behavior: "smooth", block: "start" }));
    } catch (error) {
      setFailed(error);
    } finally {
      setBusy(false);
    }
  };

  const warnings = options.reasons.map((r) => reason(r, label)).filter((r) => r !== null);

  return (
    <>
      <div className="pf-card pf-strip">
        <span>Finansal IQ'n</span>
        <b>{options.iqScore}</b>
        <Pill tone={TONE[options.segment]}>{SEGMENT[options.segment]}</Pill>
        <p>
          Risk tavanın <strong>{LEVEL[options.maxRisk].toLowerCase()}</strong>. Yatırılabilir payın <strong>{percent(options.investable.sharePercent)}</strong>: her ay {tl(options.investable.monthlyAmount)}, tek seferlik {tl(options.investable.oneTimeAmount)}.
        </p>
        <HowInvestable iq={options.iqScore} i={options.investable} />
      </div>

      {warnings.length > 0 && (
        <Banner kind="warning" title="Önce bilmen gerekenler">
          <ul>
            {warnings.map((w) => (
              <li key={w}>{w}</li>
            ))}
          </ul>
        </Banner>
      )}

      <Card title="1. Portföy türünü seç" note="Dört seçenekten birini seç; dağılımı Portföy servisi hesaplar.">
        <div className="pf-grid4" role="radiogroup" aria-label="Portföy türü">
          {options.options.map((o) => {
            const locked = options.unavailableOptions.includes(o);
            return (
              <Choice key={o} selected={option === o} locked={locked} onClick={() => setOption(o)} tag={OPTION[o].number} title={OPTION[o].title} badge={locked ? <Pill tone="blue">Hazırlanıyor</Pill> : undefined}>
                {OPTION[o].text}
              </Choice>
            );
          })}
        </div>
        {options.unavailableOptions.includes("AINVEST") && (
          <p className="pf-note">
            4.4 henüz öneri vermiyor; motorun sanal işlemlerini{" "}
            {marketOpen ? (
              <button type="button" className="pf-link" onClick={onOpenMarket}>
                Piyasa (4.4)
              </button>
            ) : (
              "Piyasa (4.4)"
            )}{" "}
            sayfasında görebilirsin{marketOpen ? "" : "; sayfa portföy seçimini kaydedince açılır"}.
          </p>
        )}
      </Card>

      <Card title="2. Risk seviyeni seç" note="Finansal IQ segmentin, seçebileceğin en yüksek seviyeyi belirler.">
        <div className="pf-grid3" role="radiogroup" aria-label="Risk seviyesi">
          {LEVELS.map((l, i) => (
            <Choice key={l} selected={risk === l} locked={i > rank} onClick={() => setRisk(l)} title={LEVEL[l]}>
              {i > rank ? "Kilitli" : RISK_TEXT[l]}
            </Choice>
          ))}
        </div>
        {rank < 2 && (
          <p className="pf-note">
            {options.maxRisk === options.segment
              ? `IQ segmentin şu an en fazla ${LEVEL[options.maxRisk].toLowerCase()} seviyesine izin veriyor; skorun yükseldikçe açılır.`
              : `IQ segmentin ${LEVEL[options.segment].toLowerCase()}, ama tavanın ${LEVEL[options.maxRisk].toLowerCase()}: en zayıf halkan belirliyor (yukarıdaki uyarılar).`}
          </p>
        )}
      </Card>

      {option === "INSTITUTION" && (
        <Card title="3. Kurumun dağılımını seç" note="Yüzdeler bizim değil: kurumların kendi yayınlarından. Kurumlarla bir bağlantımız yok.">
          <div className="pf-grid3" role="radiogroup" aria-label="Kurum">
            {options.institutionStyleInfo.map((s) => (
              <Choice key={s.code} selected={style === s.code} onClick={() => setStyle(s.code)} title={s.label}>
                {s.description}
                <small>
                  Kaynak: {s.source.name}, {month(s.source.period)}
                </small>
              </Choice>
            ))}
          </div>
        </Card>
      )}

      {option === "CUSTOM" && (
        <Card title="3. Odaklanacağın varlıkları seç" note="Seçtiklerin sepetin %60'ını eşit paylaşır; riskli varlıkların (Bitcoin, Nvidia, S&P 500, BIST 100) toplamı risk seviyenin sınırını geçemez, sınıra eşit olabilir. Güvenli varlıklar: TL mevduat, altın, euro.">
          <Chips label="Odak varlıklar" items={options.assetInfo} value={focus} disabled={excluded} onToggle={toggle(focus, setFocus)} />
        </Card>
      )}

      {(option === "CUSTOM" || option === "STANDARD") && (
        <Card title={option === "CUSTOM" ? "4. İstemediğin varlık var mı?" : "3. İstemediğin varlık var mı?"} note="İsteğe bağlı. Çıkardığın varlığın payı aynı kısımdaki diğerlerine geçer.">
          <Chips label="İstenmeyen varlıklar" items={options.assetInfo} value={excluded} disabled={option === "CUSTOM" ? focus : []} onToggle={toggle(excluded, setExcluded)} />
        </Card>
      )}

      <div className="pf-action">
        <Button onClick={calculate} busy={busy} disabled={missing.length > 0}>
          {busy ? "Hesaplanıyor…" : "Kaydet ve öneriyi hesapla"}
        </Button>
        <span>{missing.length ? `Eksik: ${missing.join(", ")}.` : "Seçimin kaydedilir, dağılım hesaplanır."}</span>
      </div>
      {failed !== null && (
        <Banner kind="danger" title="Hesaplanamadı">
          {problem(failed)}
        </Banner>
      )}

      {proposal && <ProposalCard key={proposal.createdAt} api={api} proposal={proposal} label={label} onRecalculate={calculate} canRecalculate={missing.length === 0} busy={busy} />}
    </>
  );
}

function ProposalCard({ api, proposal, label, onRecalculate, canRecalculate, busy }: { api: PortfolioApi; proposal: Proposal; label: (code: string) => string; onRecalculate: () => void; canRecalculate: boolean; busy: boolean }) {
  const p = proposal;
  const reasons = p.reasons.map((r) => reason(r, label)).filter((r) => r !== null);
  const choices = [
    OPTION[p.preferences.option].title,
    `${LEVEL[p.risk.chosen].toLowerCase()} risk`,
    p.preferences.focusAssets?.length ? `odak: ${p.preferences.focusAssets.map(label).join(", ")}` : "",
    p.preferences.excludedAssets?.length ? `istenmeyen: ${p.preferences.excludedAssets.map(label).join(", ")}` : "",
  ].filter(Boolean);
  return (
    <section id="pf-proposal" className="pf-card">
      <div className="pf-row">
        <h2>Önerin</h2>
        <small className="pf-note">{date(p.createdAt)}</small>
      </div>
      {p.stale && (
        <Banner kind="warning" title="Bu öneri eski">
          Finansal IQ skorun bu öneriden sonra yeniden hesaplandı.{" "}
          <button type="button" className="pf-link" onClick={onRecalculate} disabled={!canRecalculate || busy}>
            Yeniden hesapla
          </button>
        </Banner>
      )}
      <p className="pf-note">
        {choices.join(" · ")} · IQ {p.basedOn.iqScore} ({LEVEL[p.basedOn.segment].toLowerCase()}), skor kuralları {p.basedOn.scoringVersion}
      </p>

      <div className="pf-tiles">
        <Tile label="Yatırılabilir pay" value={percent(p.investable.sharePercent)} />
        <Tile label="Her ay" value={tl(p.investable.monthlyAmount)} />
        <Tile label="Tek seferlik" value={tl(p.investable.oneTimeAmount)} />
      </div>
      <p className="pf-note">Pay, aylık artana ve 3 aylık acil durum fonunun üstündeki nakde uygulanır. {p.investable.sharePercent === 0 && "Payın 0 olduğu için tutarlar 0; dağılım bilgi amaçlıdır."}</p>

      <h3>Dağılım</h3>
      <Distribution items={p.allocations.map((a) => ({ code: a.asset, label: a.label, percent: a.percent, amount: tl(a.amount), once: tl(a.oneTimeAmount) }))} />

      {reasons.length > 0 && (
        <>
          <h3>Gerekçeler</h3>
          <ul className="pf-list">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
        </>
      )}
      {p.source && (
        <p className="pf-note">
          Kaynak: <a href={p.source.url} target="_blank" rel="noreferrer">{p.source.name}</a>, {month(p.source.period)}
        </p>
      )}
      <Coach api={api} />
      <p className="pf-disclaimer">{p.disclaimer}</p>
    </section>
  );
}

// the AI service turns the finished numbers into sentences; it never computes
function Coach({ api }: { api: PortfolioApi }) {
  const [answer, setAnswer] = useState<Explanation | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<unknown>(null);
  const ask = async () => {
    setBusy(true);
    setFailed(null);
    try {
      setAnswer(await api.raw<Explanation>("/ai/explain-portfolio", 120000));
    } catch (error) {
      setFailed(error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <div className="pf-coach">
      <h3>Koçun açıklaması</h3>
      <div className="pf-action">
        <Button onClick={ask} busy={busy}>
          {busy ? "Açıklanıyor…" : answer ? "Yeniden açıkla" : "Öneriyi açıkla"}
        </Button>
        {busy && <span>Koç düşünüyor, yerel model 30–60 saniye sürebilir.</span>}
      </div>
      {failed !== null && <p className="pf-note">Koç şu an cevap veremiyor. {problem(failed)}</p>}
      {answer && (
        <div className="pf-answer">
          <div className="pf-row-start">
            {answer.model && <Pill>Model: {answer.model}</Pill>}
            {answer.numbersVerified && <Pill tone="good">Sayılar doğrulandı</Pill>}
            {answer.source === "sample" && <Pill tone="warn">Örnek veriyle</Pill>}
          </div>
          <p>{answer.explanation}</p>
          {answer.disclaimer && <small className="pf-note">{answer.disclaimer}</small>}
        </div>
      )}
    </div>
  );
}
