import { useCallback } from "react";
import { Link } from "react-router-dom";
import { getProfile } from "../../api/financeApi";
import {
  BILLS_ON_TIME_OPTIONS,
  BILLS_ON_TIME_QUESTION,
  LATE_PAYMENTS_OPTIONS,
  LATE_PAYMENTS_QUESTION,
  MINIMUM_PAYMENT_OPTIONS,
  MINIMUM_PAYMENT_QUESTION,
  paymentAnswerLabel,
} from "../../lib/labels";
import { ROUTES } from "../../lib/routes";
import { useAsync } from "../../lib/useAsync";
import type { PaymentHabits } from "../../types/api";
import Card from "../Card";
import ErrorBox from "../ErrorBox";
import Spinner from "../Spinner";

const NOT_ANSWERED = "Cevaplanmadı";

// The user's own answers, shown as given. Nothing is scored here: payment habits are not part of the IQ score yet.
export function PaymentHabitsView({ habits }: { habits: PaymentHabits | null }) {
  const rows = [
    { question: BILLS_ON_TIME_QUESTION, answer: paymentAnswerLabel(BILLS_ON_TIME_OPTIONS, habits?.billsOnTime) },
    { question: MINIMUM_PAYMENT_QUESTION, answer: paymentAnswerLabel(MINIMUM_PAYMENT_OPTIONS, habits?.minimumPaymentMonths) },
    { question: LATE_PAYMENTS_QUESTION, answer: paymentAnswerLabel(LATE_PAYMENTS_OPTIONS, habits?.latePayments) },
  ];

  if (rows.every((row) => row.answer === null)) {
    return (
      <div className="stack" data-testid="payment-habits-empty">
        <p className="text-sm text-secondary">Ödeme alışkanlıklarınla ilgili soruları henüz cevaplamadın.</p>
        <div>
          <Link className="btn btn-secondary btn-sm" to={ROUTES.profile}>
            Profilde cevapla
          </Link>
        </div>
      </div>
    );
  }

  return (
    <dl className="stack" data-testid="payment-habits">
      {rows.map((row) => (
        <div key={row.question}>
          <dt className="text-sm text-secondary">{row.question}</dt>
          <dd style={{ margin: 0, fontWeight: 600 }}>{row.answer ?? NOT_ANSWERED}</dd>
        </div>
      ))}
    </dl>
  );
}

// loads the saved profile (GET /api/Profiles/{userId}) for its payment habit answers
export default function PaymentHabitsCard({ className }: { className?: string }) {
  const profile = useAsync(useCallback((signal: AbortSignal) => getProfile({ signal }), []));

  let body;
  if (profile.data !== undefined) {
    body = <PaymentHabitsView habits={profile.data} />;
  } else if (profile.loading) {
    body = <Spinner label="Ödeme alışkanlıkları yükleniyor…" />;
  } else {
    body = <ErrorBox title="Ödeme alışkanlıkların yüklenemedi" error={profile.error} onRetry={profile.reload} />;
  }

  return (
    <Card title="Ödeme disiplini" subtitle="Cevapların skoru henüz etkilemiyor." className={className}>
      {body}
    </Card>
  );
}
