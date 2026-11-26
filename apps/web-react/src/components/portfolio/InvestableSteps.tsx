import { formatMoney, formatPercent } from "../../lib/format";
import type { ServiceInvestable } from "../../types/portfolioService";
import { reasonText } from "./proposal";

export interface InvestableStepsProps {
  iqScore: number;
  investable: ServiceInvestable;
}

// Where the investable share and the two amounts come from, step by step, before a proposal is computed.
// Every number is the Portfolio Service's (options.investable and its basis); nothing is computed here.
export default function InvestableSteps({ iqScore, investable }: InvestableStepsProps) {
  const { basis, sharePercent, monthlyAmount, oneTimeAmount } = investable;
  const share = formatPercent(sharePercent);
  const reasons = investable.reasons ?? [];

  return (
    <div className="stack">
      <div className="stat-row">
        <div className="stat-tile">
          <span className="stat-label">Yatırılabilir pay</span>
          <span className="stat-value">{share}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Her ay</span>
          <span className="stat-value">{formatMoney(monthlyAmount)}</span>
        </div>
        <div className="stat-tile">
          <span className="stat-label">Tek seferlik</span>
          <span className="stat-value">{formatMoney(oneTimeAmount)}</span>
        </div>
      </div>

      {basis ? (
        <ol className="investable-steps text-sm">
          <li>
            <span className="investable-step-title">Yatırılabilir pay</span>
            Finansal IQ'n {iqScore}; pay IQ − 30 kuralıyla belirlenir (en az %0, en çok %70) → <strong>{share}</strong>.
          </li>
          <li>
            <span className="investable-step-title">Aylık artı</span>
            Gelir {formatMoney(basis.monthlyIncome)} − gider {formatMoney(basis.monthlyExpenses)} − taksit{" "}
            {formatMoney(basis.monthlyDebtPayment)} = <strong>{formatMoney(basis.monthlySurplus)}</strong>. Pay ({share}) uygulanınca →{" "}
            <strong>her ay {formatMoney(monthlyAmount)}</strong>.
          </li>
          <li>
            <span className="investable-step-title">Acil durum fonu</span>
            {basis.reserveMonths} aylık gider = <strong>{formatMoney(basis.emergencyFund)}</strong>. Acil fon kontrolünde nakdin tamamı
            ve yatırımlarının yarısı sayılır: {formatMoney(basis.reserve)}.
          </li>
          <li>
            <span className="investable-step-title">Serbest nakit</span>
            Nakdin {formatMoney(basis.cashReserve)}; acil durum fonunun üstünde kalan <strong>{formatMoney(basis.freeCash)}</strong>.
            Pay ({share}) uygulanınca → <strong>tek seferlik {formatMoney(oneTimeAmount)}</strong>.
          </li>
        </ol>
      ) : null}

      {reasons.length > 0 ? (
        <ul className="proposal-reasons">
          {reasons.map((code) => (
            <li key={code}>{reasonText(code).text}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
