import { useCallback, useState, type FormEvent } from "react";
import { ApiError, type PortfolioApi } from "./api";
import { problem } from "./text";
import { Banner, Button, Card, Loading } from "./ui";
import { useLoad } from "./useLoad";

type Amount = "monthlyIncome" | "monthlyExpenses" | "monthlyDebtPayment" | "totalDebt" | "cashReserve" | "investmentAmount";
type Profile = Record<Amount, number> & { impatienceLevel: number };

const GROUPS: { title: string; note: string; fields: { key: Amount; label: string; hint: string }[] }[] = [
  {
    title: "Aylık durum",
    note: "Her ay düzenli olarak giren ve çıkan para",
    fields: [
      { key: "monthlyIncome", label: "Aylık gelir", hint: "Maaş ve diğer düzenli gelirlerin toplamı (net)." },
      { key: "monthlyExpenses", label: "Aylık gider", hint: "Kira, faturalar, mutfak gibi düzenli harcamalar (taksitler hariç)." },
      { key: "monthlyDebtPayment", label: "Aylık taksit", hint: "Kredi ve kart taksitlerinin aylık toplamı." },
    ],
  },
  {
    title: "Varlıklar ve borçlar",
    note: "Bugünkü toplam tutarlar",
    fields: [
      { key: "totalDebt", label: "Toplam borç", hint: "Kalan kredi ve kart borçlarının toplamı." },
      { key: "cashReserve", label: "Nakit birikim", hint: "Hemen kullanılabilir nakit ve mevduat." },
      { key: "investmentAmount", label: "Yatırımlar", hint: "Altın, döviz, fon, hisse gibi yatırımların bugünkü değeri." },
    ],
  },
];
const EMPTY: Profile = { monthlyIncome: 0, monthlyExpenses: 0, monthlyDebtPayment: 0, totalDebt: 0, cashReserve: 0, investmentAmount: 0, impatienceLevel: 3 };
const PATIENCE = ["Yıllarca", "Bir iki yıl", "Birkaç ay", "Birkaç hafta", "Hemen"];

export default function ProfilePage({ api, onDone }: { api: PortfolioApi; onDone: () => void }) {
  const path = `/api/Profiles/${encodeURIComponent(api.userId)}`;
  const load = useCallback(
    () =>
      api.get<Profile>(path).catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }),
    [api, path],
  );
  const { data, error, loading } = useLoad(load);
  return (
    <>
      <header className="pf-head">
        <h1>Finansal profil</h1>
        <p>Gelir, gider, borç ve birikim bilgilerin Finansal IQ skorunun temelidir.</p>
      </header>
      {loading ? (
        <Loading />
      ) : error !== null ? (
        <Banner kind="danger" title="Yüklenemedi">
          {problem(error)}
        </Banner>
      ) : (
        <ProfileForm api={api} path={path} saved={data} onDone={onDone} />
      )}
    </>
  );
}

// digits only, shown grouped: "30.000" can never be read as 30
const digits = (text: string) => text.replace(/\D/g, "").slice(0, 15);
const grouped = (text: string) => text.replace(/\B(?=(\d{3})+$)/g, ".");

function ProfileForm({ api, path, saved, onDone }: { api: PortfolioApi; path: string; saved: Profile | null; onDone: () => void }) {
  const start = saved ?? EMPTY;
  const [amounts, setAmounts] = useState<Record<Amount, string>>(() => {
    const out = {} as Record<Amount, string>;
    for (const g of GROUPS) for (const f of g.fields) out[f.key] = start[f.key] ? String(Math.round(start[f.key])) : "";
    return out;
  });
  const [impatience, setImpatience] = useState(start.impatienceLevel || 3);
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<unknown>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setFailed(null);
    try {
      const body: Record<string, number> = { impatienceLevel: impatience };
      for (const [k, v] of Object.entries(amounts)) body[k] = Number(v || 0);
      await api.send("PUT", path, body);
      await api.send("POST", `${path}/calculate-iq`);
      onDone();
    } catch (error) {
      setFailed(error);
      setBusy(false);
    }
  };

  return (
    <form className="pf-form" onSubmit={submit}>
      {!saved && (
        <Banner title="Henüz kayıtlı profilin yok">Bilgilerini gir ve Finansal IQ skorunu hesapla. Tutarları TL olarak, kuruşsuz yaz; boş bıraktığın alanlar 0 sayılır.</Banner>
      )}
      {GROUPS.map((g) => (
        <Card key={g.title} title={g.title} note={g.note}>
          <div className="pf-grid2">
            {g.fields.map((f) => (
              <label key={f.key}>
                {f.label}
                <span className="pf-money">
                  <input inputMode="numeric" placeholder="0" value={grouped(amounts[f.key])} onChange={(e) => setAmounts((old) => ({ ...old, [f.key]: digits(e.target.value) }))} />
                  <i>TL</i>
                </span>
                <small>{f.hint}</small>
              </label>
            ))}
          </div>
        </Card>
      ))}
      <Card title="Yatırım sabrın" note="Yatırımının getirisini görmek için ne kadar bekleyebilirsin? (1 sabırlı – 5 çok sabırsız)">
        <div className="pf-chips" role="radiogroup" aria-label="Yatırım sabrı">
          {PATIENCE.map((text, i) => (
            <button key={text} type="button" role="radio" aria-checked={impatience === i + 1} className={`pf-chip${impatience === i + 1 ? " pf-on" : ""}`} onClick={() => setImpatience(i + 1)}>
              {i + 1} · {text}
            </button>
          ))}
        </div>
      </Card>
      {failed !== null && (
        <Banner kind="danger" title="Kaydedilemedi">
          {problem(failed)}
        </Banner>
      )}
      <div className="pf-action">
        <Button type="submit" busy={busy} disabled={!amounts.monthlyIncome}>
          {busy ? "Hesaplanıyor…" : "Kaydet ve hesapla"}
        </Button>
        <span>{amounts.monthlyIncome ? "Profilin kaydedilir, Finansal IQ skorun hesaplanır ve portföy açılır." : "En az aylık gelirini gir."}</span>
      </div>
    </form>
  );
}
