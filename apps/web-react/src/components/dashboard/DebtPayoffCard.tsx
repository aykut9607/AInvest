import { useCallback, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { getDebtPayoff, type DebtPayoffResult } from "../../api/financeApi";
import { formatMoney, formatPercent } from "../../lib/format";
import { ROUTES } from "../../lib/routes";
import { useAsync } from "../../lib/useAsync";
import type { DebtPayoff } from "../../types/api";
import Button from "../Button";
import Card from "../Card";
import ErrorBox from "../ErrorBox";
import Field from "../Field";
import Notice from "../Notice";
import Spinner from "../Spinner";
import DebtBalanceChart from "./DebtBalanceChart";
import {
  DEFAULT_INTEREST_PERCENT,
  debtState,
  formatMonths,
  parsePercentInput,
  percentToRate,
  percentToText,
} from "./dashboardData";

export function DebtScheduleTable({ payoff }: { payoff: DebtPayoff }) {
  return (
    <div className="table-wrap debt-table-wrap">
      <table className="table dash-table" data-testid="debt-table">
        <caption className="visually-hidden">Aylık borç ödeme tablosu</caption>
        <thead>
          <tr>
            <th scope="col" className="num">
              Ay
            </th>
            <th scope="col" className="num">
              Ay başı borç
            </th>
            <th scope="col" className="num">
              Faiz
            </th>
            <th scope="col" className="num">
              Taksit
            </th>
            <th scope="col" className="num">
              Anapara
            </th>
            <th scope="col" className="num">
              Ay sonu borç
            </th>
          </tr>
        </thead>
        <tbody>
          {payoff.schedule.map((month) => (
            <tr key={month.month}>
              <td className="num">{month.month}</td>
              <td className="num">{formatMoney(month.openingBalance)}</td>
              <td className="num">{formatMoney(month.interest)}</td>
              <td className="num">{formatMoney(month.payment)}</td>
              <td className="num">{formatMoney(month.principal)}</td>
              <td className="num">{formatMoney(month.closingBalance)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Inputs({ payoff }: { payoff: DebtPayoff }) {
  return (
    <dl className="kv">
      <dt>Toplam borç</dt>
      <dd>{formatMoney(payoff.totalDebt)}</dd>
      <dt>Aylık taksit</dt>
      <dd>{formatMoney(payoff.monthlyPayment)}</dd>
      <dt>Aylık faiz oranı</dt>
      <dd>{formatPercent(payoff.monthlyInterestRate, { ratio: true, fractionDigits: 2 })}</dd>
    </dl>
  );
}

function NoDebt() {
  return (
    <div className="dash-calm" role="status">
      <svg className="dash-calm-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M8 12.5l2.5 2.5L16 9.5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
      <div>
        <p className="dash-calm-title">Borcun yok</p>
        <p className="text-sm text-secondary">Kayıtlı profilinde ödenecek bir borç görünmüyor.</p>
      </div>
    </div>
  );
}

// what the service answered, without the loading and the interest form (rendered on its own in tests)
export function DebtPayoffBody({ result, showTable }: { result: DebtPayoffResult; showTable: boolean }) {
  const { payoff } = result;
  const state = debtState(payoff);
  if (state === "no-debt") return <NoDebt />;

  // no schedule when the installment does not even cover the first month's interest
  let visual = null;
  if (payoff.schedule.length > 0) {
    visual = showTable ? <DebtScheduleTable payoff={payoff} /> : <DebtBalanceChart payoff={payoff} />;
  }

  if (state === "not-paid-off") {
    return (
      <div className="stack">
        <Notice tone="warning" title="Bu taksitle borç kapanmıyor">
          {result.message || "Bu taksitle borç kapanmıyor."} Taksidi artırmak ya da faiz oranını değiştirip yeniden
          hesaplamak sonucu değiştirir.
        </Notice>
        <Inputs payoff={payoff} />
        {visual}
      </div>
    );
  }

  return (
    <div className="stack">
      <div className="stat-row">
        <div className="stat">
          <p className="stat-label">Borcun kapanma süresi</p>
          <p className="stat-value" data-testid="debt-months">
            {payoff.months !== null ? formatMonths(payoff.months) : "–"}
          </p>
        </div>
        <div className="stat">
          <p className="stat-label">Toplam faiz</p>
          <p className="stat-value">{formatMoney(payoff.totalInterest)}</p>
        </div>
        <div className="stat">
          <p className="stat-label">Toplam ödeme</p>
          <p className="stat-value">{formatMoney(payoff.totalPaid)}</p>
        </div>
      </div>
      <Inputs payoff={payoff} />
      {visual}
    </div>
  );
}

// GET /api/Profiles/{userId}/debt-payoff with the saved debt and installment and a monthly interest the user picks
export default function DebtPayoffCard({ className }: { className?: string }) {
  const [rateText, setRateText] = useState(() => percentToText(DEFAULT_INTEREST_PERCENT));
  const [ratePercent, setRatePercent] = useState(DEFAULT_INTEREST_PERCENT);
  const [rateError, setRateError] = useState<string | null>(null);
  const [showTable, setShowTable] = useState(false);
  const payoff = useAsync(
    useCallback((signal: AbortSignal) => getDebtPayoff(percentToRate(ratePercent), { signal }), [ratePercent])
  );

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const parsed = parsePercentInput(rateText);
    if (!parsed.ok) {
      setRateError(parsed.error);
      return;
    }
    setRateError(null);
    if (parsed.value === ratePercent) payoff.reload();
    else setRatePercent(parsed.value);
  };

  const data = payoff.data;
  const hasDebt = data ? debtState(data.payoff) !== "no-debt" : false;
  const hasSchedule = data ? data.payoff.schedule.length > 0 : false;

  let body;
  if (data === undefined && payoff.loading) {
    body = <Spinner label="Borç ödeme planı hesaplanıyor…" />;
  } else if (data === undefined) {
    body = <ErrorBox title="Borç ödeme planı hesaplanamadı" error={payoff.error} onRetry={payoff.reload} />;
  } else if (data === null) {
    body = (
      <div className="stack-sm">
        <p className="text-secondary">Kayıtlı finansal profilin bulunamadı.</p>
        <div>
          <Link className="btn btn-secondary btn-sm" to={ROUTES.profile}>
            Profilini gir
          </Link>
        </div>
      </div>
    );
  } else if (!hasDebt) {
    body = <DebtPayoffBody result={data} showTable={showTable} />;
  } else {
    body = (
      <div className="stack">
        <form className="debt-rate-form" onSubmit={handleSubmit} noValidate aria-label="Faiz oranı">
          <Field
            label="Aylık faiz oranı"
            name="monthlyInterestPercent"
            inputMode="decimal"
            autoComplete="off"
            suffix="%"
            value={rateText}
            onChange={(event) => {
              setRateText(event.target.value);
              setRateError(null);
            }}
            error={rateError}
            hint="Varsayılan %3,5; faizsiz taksit için 0 yaz."
          />
          <Button type="submit" loading={payoff.loading} loadingLabel="Hesaplanıyor…">
            Yeniden hesapla
          </Button>
        </form>
        <ErrorBox error={payoff.error} title="Yeni oranla hesaplanamadı" onRetry={payoff.reload} />
        <div className={payoff.loading ? "is-refreshing" : undefined}>
          <DebtPayoffBody result={data} showTable={showTable} />
        </div>
      </div>
    );
  }

  return (
    <Card
      title="Borç ödeme planı"
      subtitle="Kayıtlı toplam borcun ve aylık taksitinle borcun ne zaman biter?"
      className={className}
      actions={
        hasSchedule ? (
          <Button size="sm" className="dash-toggle" aria-pressed={showTable} onClick={() => setShowTable((value) => !value)}>
            Tablo
          </Button>
        ) : null
      }
    >
      {body}
    </Card>
  );
}
