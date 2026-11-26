import { useCallback, useState, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { calculateIq, getProfile, saveProfile } from "../api/financeApi";
import AmountField from "../components/AmountField";
import Button from "../components/Button";
import Card from "../components/Card";
import ErrorBox from "../components/ErrorBox";
import Notice from "../components/Notice";
import PageHeader from "../components/PageHeader";
import SegmentedControl from "../components/SegmentedControl";
import Spinner from "../components/Spinner";
import { wholeAmountDigits } from "../lib/format";
import {
  BILLS_ON_TIME_OPTIONS,
  BILLS_ON_TIME_QUESTION,
  IMPATIENCE_HINTS,
  IMPATIENCE_LEVELS,
  LATE_PAYMENTS_OPTIONS,
  LATE_PAYMENTS_QUESTION,
  MINIMUM_PAYMENT_OPTIONS,
  MINIMUM_PAYMENT_QUESTION,
} from "../lib/labels";
import { ROUTES, type DashboardLocationState } from "../lib/routes";
import { useAsync } from "../lib/useAsync";
import type { BillsOnTime, FinancialProfile, LatePayments, MinimumPaymentMonths, ProfileInput } from "../types/api";

type HabitKey = "billsOnTime" | "minimumPaymentMonths" | "latePayments";
type AmountKey = Exclude<keyof ProfileInput, "impatienceLevel" | HabitKey>;

// "" = not answered (sent as nothing, stored as null)
const UNANSWERED = "";
const UNANSWERED_LABEL = "Boş bırak";

// amounts as digit strings while typing, converted on submit; empty fields count as 0
interface FormValues extends Record<AmountKey, string> {
  impatienceLevel: number;
  billsOnTime: BillsOnTime | typeof UNANSWERED;
  minimumPaymentMonths: MinimumPaymentMonths | typeof UNANSWERED;
  latePayments: LatePayments | typeof UNANSWERED;
}

const EMPTY_FORM: FormValues = {
  monthlyIncome: "",
  monthlyExpenses: "",
  monthlyDebtPayment: "",
  totalDebt: "",
  cashReserve: "",
  investmentAmount: "",
  impatienceLevel: 3,
  billsOnTime: UNANSWERED,
  minimumPaymentMonths: UNANSWERED,
  latePayments: UNANSWERED,
};

// a stored answer the form knows, otherwise unanswered
function knownAnswer<T extends string>(options: { value: T }[], value: T | null | undefined): T | typeof UNANSWERED {
  return options.some((option) => option.value === value) ? (value as T) : UNANSWERED;
}

function formFromProfile(profile: FinancialProfile | null): FormValues {
  if (!profile) return EMPTY_FORM;
  return {
    monthlyIncome: wholeAmountDigits(profile.monthlyIncome),
    monthlyExpenses: wholeAmountDigits(profile.monthlyExpenses),
    monthlyDebtPayment: wholeAmountDigits(profile.monthlyDebtPayment),
    totalDebt: wholeAmountDigits(profile.totalDebt),
    cashReserve: wholeAmountDigits(profile.cashReserve),
    investmentAmount: wholeAmountDigits(profile.investmentAmount),
    impatienceLevel: profile.impatienceLevel >= 1 && profile.impatienceLevel <= 5 ? profile.impatienceLevel : 3,
    billsOnTime: knownAnswer(BILLS_ON_TIME_OPTIONS, profile.billsOnTime),
    minimumPaymentMonths: knownAnswer(MINIMUM_PAYMENT_OPTIONS, profile.minimumPaymentMonths),
    latePayments: knownAnswer(LATE_PAYMENTS_OPTIONS, profile.latePayments),
  };
}

const toAmount = (digits: string) => (digits ? Number(digits) : 0);

const MONTHLY_FIELDS: { key: AmountKey; label: string; hint: string }[] = [
  { key: "monthlyIncome", label: "Aylık gelir", hint: "Maaş ve diğer düzenli gelirlerin toplamı (net)." },
  { key: "monthlyExpenses", label: "Aylık gider", hint: "Kira, faturalar, mutfak gibi düzenli harcamalar (taksitler hariç)." },
  { key: "monthlyDebtPayment", label: "Aylık taksit", hint: "Kredi ve kart taksitlerinin aylık toplamı." },
];

const BALANCE_FIELDS: { key: AmountKey; label: string; hint: string }[] = [
  { key: "totalDebt", label: "Toplam borç", hint: "Kalan kredi ve kart borçlarının toplamı." },
  { key: "cashReserve", label: "Nakit birikim", hint: "Hemen kullanılabilir nakit ve vadesiz/vadeli mevduat." },
  { key: "investmentAmount", label: "Yatırımlar", hint: "Altın, döviz, fon, hisse gibi yatırımların bugünkü değeri." },
];

export function ProfileForm({ profile }: { profile: FinancialProfile | null }) {
  const navigate = useNavigate();
  const [values, setValues] = useState<FormValues>(() => formFromProfile(profile));
  const [incomeError, setIncomeError] = useState<string | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [errorTitle, setErrorTitle] = useState<string | undefined>(undefined);
  const [submitting, setSubmitting] = useState(false);

  const setAmount = (key: AmountKey) => (digits: string) => {
    setValues((previous) => ({ ...previous, [key]: digits }));
    if (key === "monthlyIncome") setIncomeError(null);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!(toAmount(values.monthlyIncome) > 0)) {
      setIncomeError("Aylık gelir sıfırdan büyük olmalı.");
      return;
    }

    const input: ProfileInput = {
      monthlyIncome: toAmount(values.monthlyIncome),
      monthlyExpenses: toAmount(values.monthlyExpenses),
      monthlyDebtPayment: toAmount(values.monthlyDebtPayment),
      totalDebt: toAmount(values.totalDebt),
      cashReserve: toAmount(values.cashReserve),
      investmentAmount: toAmount(values.investmentAmount),
      impatienceLevel: values.impatienceLevel,
      billsOnTime: values.billsOnTime || null,
      minimumPaymentMonths: values.minimumPaymentMonths || null,
      latePayments: values.latePayments || null,
    };

    setSubmitting(true);
    setError(null);
    setErrorTitle(undefined);
    try {
      await saveProfile(input);
    } catch (err) {
      setErrorTitle("Profil kaydedilemedi");
      setError(err);
      setSubmitting(false);
      return;
    }
    try {
      const calculation = await calculateIq();
      const state: DashboardLocationState = { calculation };
      navigate(ROUTES.dashboard, { state });
    } catch (err) {
      setErrorTitle("Profil kaydedildi, ancak skor hesaplanamadı");
      setError(err);
      setSubmitting(false);
    }
  };

  const renderAmount = (field: { key: AmountKey; label: string; hint: string }) => (
    <AmountField
      key={field.key}
      name={field.key}
      label={field.label}
      hint={field.hint}
      value={values[field.key]}
      onChange={setAmount(field.key)}
      error={field.key === "monthlyIncome" ? incomeError : null}
      required={field.key === "monthlyIncome"}
    />
  );

  return (
    <form className="stack-lg" onSubmit={handleSubmit} noValidate aria-label="Finansal profil formu">
      {!profile ? (
        <Notice title="Henüz kayıtlı profilin yok">
          Bilgilerini gir ve Finansal IQ skorunu hesapla. Tutarları TL olarak, kuruşsuz yaz; boş bıraktığın alanlar 0 sayılır.
        </Notice>
      ) : null}

      <Card title="Aylık durum" subtitle="Her ay düzenli olarak giren ve çıkan para">
        <div className="form-grid">{MONTHLY_FIELDS.map(renderAmount)}</div>
      </Card>

      <Card title="Varlıklar ve borçlar" subtitle="Bugünkü toplam tutarlar">
        <div className="form-grid">{BALANCE_FIELDS.map(renderAmount)}</div>
      </Card>

      <Card title="Yatırım sabrın">
        <SegmentedControl<number>
          name="impatienceLevel"
          legend="Yatırımının getirisini görmek için ne kadar bekleyebilirsin? (1 sabırlı – 5 çok sabırsız)"
          value={values.impatienceLevel}
          onChange={(impatienceLevel) => setValues((previous) => ({ ...previous, impatienceLevel }))}
          options={IMPATIENCE_LEVELS.map((level) => ({
            value: level,
            label: String(level),
            description: IMPATIENCE_HINTS[level],
          }))}
        />
      </Card>

      <Card title="Ödeme alışkanlıkları (isteğe bağlı)" subtitle="Bu cevaplar şimdilik skoru değiştirmez; ileride skora eklenecek.">
        <div className="stack">
          <SegmentedControl<BillsOnTime | typeof UNANSWERED>
            name="billsOnTime"
            className="segmented-wrap"
            legend={BILLS_ON_TIME_QUESTION}
            value={values.billsOnTime}
            onChange={(billsOnTime) => setValues((previous) => ({ ...previous, billsOnTime }))}
            options={[...BILLS_ON_TIME_OPTIONS, { value: UNANSWERED, label: UNANSWERED_LABEL }]}
          />
          <SegmentedControl<MinimumPaymentMonths | typeof UNANSWERED>
            name="minimumPaymentMonths"
            className="segmented-wrap"
            legend={MINIMUM_PAYMENT_QUESTION}
            value={values.minimumPaymentMonths}
            onChange={(minimumPaymentMonths) => setValues((previous) => ({ ...previous, minimumPaymentMonths }))}
            options={[...MINIMUM_PAYMENT_OPTIONS, { value: UNANSWERED, label: UNANSWERED_LABEL }]}
          />
          <SegmentedControl<LatePayments | typeof UNANSWERED>
            name="latePayments"
            className="segmented-wrap"
            legend={LATE_PAYMENTS_QUESTION}
            value={values.latePayments}
            onChange={(latePayments) => setValues((previous) => ({ ...previous, latePayments }))}
            options={[...LATE_PAYMENTS_OPTIONS, { value: UNANSWERED, label: UNANSWERED_LABEL }]}
          />
        </div>
      </Card>

      <ErrorBox error={error} title={errorTitle} onRateLimitDone={() => setError(null)} />

      <div className="form-actions">
        <Button type="submit" variant="primary" loading={submitting} loadingLabel="Hesaplanıyor…">
          Kaydet ve hesapla
        </Button>
        <p className="text-sm text-muted">
          Profilin kaydedilir, ardından Finansal IQ skorun yeniden hesaplanır.
        </p>
      </div>
    </form>
  );
}

export default function ProfilePage() {
  const profile = useAsync(useCallback((signal: AbortSignal) => getProfile({ signal }), []));

  return (
    <div className="page page-narrow">
      <PageHeader
        title="Finansal profil"
        description="Gelir, gider, borç ve birikim bilgilerin Finansal IQ skorunun temelidir. Bilgilerini güncel tut."
      />
      {profile.loading && profile.data === undefined ? (
        <Spinner layout="block" label="Profil yükleniyor…" />
      ) : profile.error ? (
        <ErrorBox title="Profil yüklenemedi" error={profile.error} onRetry={profile.reload} />
      ) : (
        <ProfileForm profile={profile.data ?? null} />
      )}
    </div>
  );
}
