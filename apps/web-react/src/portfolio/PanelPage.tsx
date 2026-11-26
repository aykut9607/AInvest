import { useState } from "react";
import type { PortfolioApi } from "./api";
import { SEGMENT, date, problem } from "./text";
import type { Explanation, IqResult, Level } from "./types";
import { Banner, Button, Card, Pill } from "./ui";

const TONE: Record<Level, "good" | "warn" | "bad"> = { HIGH: "good", MEDIUM: "warn", LOW: "bad" };
const COLOR: Record<Level, string> = { HIGH: "var(--good)", MEDIUM: "var(--warn)", LOW: "var(--bad)" };
const SUMMARY: Record<Level, string> = { HIGH: "Finansal durumun güçlü.", MEDIUM: "Finansal durumun dengeli, bazı alanlar güçlendirilmeli.", LOW: "Finansal durumun kırılgan; önce temeli güçlendir." };

// factor names; the maximums come with the result (v3: factorMaximums), v2 results without them use the v2 table
const FACTOR: Record<string, string> = {
  CashReserveMonths: "Nakit rezervi",
  InstallmentToIncome: "Taksit / gelir",
  NetDebtToIncome: "Net borç / gelir",
  DebtToIncomeRatio: "Borç / gelir oranı",
  SavingsRate: "Tasarruf oranı",
  ExpenseRatio: "Gider oranı",
  Impatience: "Sabır",
};
const V2_MAX: Record<string, number> = { CashReserveMonths: 25, DebtToIncomeRatio: 25, SavingsRate: 25, ExpenseRatio: 15, Impatience: 10 };
const WARNING: Record<string, string> = {
  "Low cash reserve": "Acil durum fonun düşük; en az 3 aylık gider önerilir.",
  "High debt burden": "Aylık taksitlerin gelirine göre yüksek.",
  "Elevated debt burden": "Aylık taksitlerin gelirine göre yükseğe yakın.",
  "High total debt": "Toplam borcun gelirine göre yüksek.",
  "Elevated total debt": "Toplam borcun gelirine göre yükseğe yakın.",
  "Negative savings rate": "Giderlerin ve taksitlerin gelirini aşıyor.",
  "Low savings rate": "Tasarruf oranın düşük.",
  "Overspending relative to income": "Giderlerin gelirine göre yüksek.",
  "High impatience": "Yatırım sabrın düşük; acele karar riski.",
  "Extreme total debt": "Toplam borcun çok yüksek.",
  "Installment below interest": "Taksitin borcun faizini karşılamıyor olabilir.",
  "Expenses look too low": "Girdiğin giderler gerçekçi görünmüyor; kontrol et.",
  "Installment without debt": "Taksit girmişsin ama toplam borç 0.",
  "Installment exceeds total debt": "Aylık taksitin toplam borçtan büyük; kontrol et.",
};
const RULE: Record<string, string> = {
  VERY_HIGH_INCOME: "Aylık gelirin 1.000.000 TL ve üzeri, net borcun düşük: skor 100.",
  VERY_HIGH_WEALTH: "Net servetin 10.000.000 TL ve üzeri: skor 100.",
  EXTREME_DEBT: "Net borcun 100.000.000 TL ve üzeri: skor 0.",
  SOLVENCY_CAP: "Net borcun yıllık gelirinin 5 katını aşıyor: bütün faktörler küçültüldü (15 katta 0).",
  WEALTH_RUNWAY: "Nakit ve yatırımların giderlerini uzun yıllar karşılıyor: skor bu yüzden yükseldi.",
};

const ADJUSTMENT: Record<string, string> = {
  WEALTH_FLOOR: "net servetin yıllık gider ve taksitlerini uzun yıllar karşıladığı için",
  INCOME_FLOOR: "gelirin çok yüksek ve borcun az olduğu için",
  DEBT_CAP: "net borcun yıllık gelirinin 3 katını aştığı için",
};

export default function PanelPage({ api, iq, onNext, onEdit }: { api: PortfolioApi; iq: IqResult; onNext: () => void; onEdit: () => void }) {
  const b = iq.factorBreakdown;
  const turn = 2 * Math.PI * 52;
  return (
    <>
      <header className="pf-head">
        <h1>Finansal IQ</h1>
        <p>Skorun, nereden geldiği ve koçun açıklaması. Portföy önerisi bu skora dayanır.</p>
      </header>
      <div className="pf-grid2">
        <Card title="Finansal IQ skorun">
          <div className="pf-ring">
            <svg viewBox="0 0 120 120" role="img" aria-label={`Skor ${iq.score} / 100`}>
              <circle cx="60" cy="60" r="52" className="pf-ring-track" />
              <circle cx="60" cy="60" r="52" className="pf-ring-value" style={{ stroke: COLOR[iq.segment], strokeDasharray: `${(iq.score / 100) * turn} ${turn}` }} />
              <text x="60" y="62" textAnchor="middle" className="pf-ring-number">
                {iq.score}
              </text>
              <text x="60" y="80" textAnchor="middle">
                / 100
              </text>
            </svg>
            <div>
              <Pill tone={TONE[iq.segment]}>{SEGMENT[iq.segment]}</Pill>
              <p>{SUMMARY[iq.segment]}</p>
              <p className="pf-note">
                Hesaplanma {date(iq.updatedAt ?? iq.createdAt)}
                {b?.version ? ` · skor kuralları ${b.version}` : ""}
              </p>
              <Button kind="quiet" onClick={onEdit}>
                Profili düzenle
              </Button>
            </div>
          </div>
        </Card>
        <Card title="Skor dökümü" note="Her faktörün aldığı puan; toplamları skoru verir.">
          <div className="pf-factors">
            {Object.entries(b?.factors ?? {}).map(([k, v]) => {
              const max = b?.factorMaximums?.[k] ?? (!b?.version || b.version.startsWith("v2") ? V2_MAX[k] : undefined);
              const share = max ? v / max : null;
              return (
                <div key={k}>
                  <span>{FACTOR[k] ?? k}</span>
                  <em>{max ? `${v} / ${max}` : v}</em>
                  <i>
                    <b style={{ width: `${100 * (share ?? v / 30)}%`, background: share === null ? "#3987e5" : share >= 0.7 ? "var(--good)" : share >= 0.4 ? "var(--warn)" : "var(--bad)" }} />
                  </i>
                </div>
              );
            })}
          </div>
          {b?.appliedRule && <p className="pf-note">{RULE[b.appliedRule] ?? `Uygulanan kural: ${b.appliedRule}`}</p>}
          {b?.adjustment && (
            <p className="pf-note">
              Faktörlerin toplamı {b.adjustment.fromFactors}; {ADJUSTMENT[b.adjustment.rule] ?? b.adjustment.rule} skor {b.adjustment.score}.
            </p>
          )}
        </Card>
      </div>
      {b && b.warnings.length > 0 && (
        <Banner kind="warning" title="Uyarılar">
          <ul>
            {b.warnings.map((w) => (
              <li key={w}>{WARNING[w] ?? w}</li>
            ))}
          </ul>
        </Banner>
      )}
      <Card title="Koç" note="Yapay zekâ koçu skorunu ve faktörlerini açıklar; rakamları kod hesaplar, koç yalnız anlatır.">
        <IqCoach api={api} iq={iq} />
      </Card>
      <div className="pf-action">
        <Button onClick={onNext}>Portföyümü oluştur</Button>
        <span>Skorun hazır; sırada portföy türü ve risk seçimi var.</span>
      </div>
    </>
  );
}

function IqCoach({ api, iq }: { api: PortfolioApi; iq: IqResult }) {
  const [answer, setAnswer] = useState<Explanation | null>(null);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<unknown>(null);
  const ask = async () => {
    setBusy(true);
    setFailed(null);
    try {
      setAnswer(await api.raw<Explanation>("/ai/explain-financial-iq", 120000, { score: iq.score, segment: iq.segment, factorBreakdown: iq.factorBreakdown }));
    } catch (error) {
      setFailed(error);
    } finally {
      setBusy(false);
    }
  };
  return (
    <>
      <div className="pf-action">
        <Button onClick={ask} busy={busy}>
          {busy ? "Açıklanıyor…" : answer ? "Yeniden açıkla" : "Skorumu açıkla"}
        </Button>
        {busy && <span>Koç düşünüyor, yerel model 30–60 saniye sürebilir.</span>}
      </div>
      {failed !== null && <p className="pf-note">Koç şu an cevap veremiyor. {problem(failed)}</p>}
      {answer && (
        <div className="pf-answer">
          <div className="pf-row-start">
            {answer.model && <Pill>Model: {answer.model}</Pill>}
            {answer.numbersVerified && <Pill tone="good">Sayılar doğrulandı</Pill>}
          </div>
          <p>{answer.explanation}</p>
          {answer.disclaimer && <small className="pf-note">{answer.disclaimer}</small>}
        </div>
      )}
    </>
  );
}
