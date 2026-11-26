import { formatMoney } from "../../lib/format";
import type { DebtPayoff } from "../../types/api";
import { axisAmountLabel, ticksWithin, zeroBasedTicks } from "./chartMath";
import { balanceSeries, type BalancePoint } from "./dashboardData";
import LineChart, { type ChartTick } from "./LineChart";

function monthLabel(month: number): string {
  return month === 0 ? "Bugün" : `${month}. ay`;
}

function describeBalance(point: BalancePoint): string {
  if (point.month === 0) return `Bugün borç ${formatMoney(point.balance)}.`;
  const parts = [`${point.month}. ay sonunda kalan borç ${formatMoney(point.balance)}`];
  if (point.interest !== null) parts.push(`bu ay faiz ${formatMoney(point.interest)}`);
  if (point.principal !== null) parts.push(`anapara ${formatMoney(point.principal)}`);
  return `${parts.join(", ")}.`;
}

function BalanceTooltip({ point }: { point: BalancePoint }) {
  return (
    <>
      <p className="chart-tooltip-title">{point.month === 0 ? "Bugün" : `${point.month}. ay sonunda`}</p>
      <p className="chart-tooltip-value">
        <span className="chart-key-line" aria-hidden="true" />
        <strong>{formatMoney(point.balance)}</strong>
        <span className="chart-tooltip-name">{point.month === 0 ? "borç" : "kalan borç"}</span>
      </p>
      {point.interest !== null && point.principal !== null ? (
        <dl className="chart-tooltip-rows">
          <dt>Faiz</dt>
          <dd>{formatMoney(point.interest)}</dd>
          <dt>Anapara</dt>
          <dd>{formatMoney(point.principal)}</dd>
        </dl>
      ) : null}
    </>
  );
}

// remaining debt month by month (closing balance of the schedule), month 0 = today's debt; area under a 2px line
export default function DebtBalanceChart({ payoff }: { payoff: DebtPayoff }) {
  const series = balanceSeries(payoff);
  if (series.length < 2) return null;

  const lastMonth = series[series.length - 1].month;
  const maxBalance = Math.max(...series.map((p) => p.balance));
  const yValues = zeroBasedTicks(maxBalance, 4);
  const yMax = yValues[yValues.length - 1];
  const yTicks: ChartTick[] = yValues.map((value) => ({ value, label: axisAmountLabel(value, yMax) }));
  const longestLabel = Math.max(...yTicks.map((t) => t.label.length));

  const xTicks = (plotWidth: number): ChartTick[] =>
    ticksWithin(lastMonth, Math.max(2, Math.floor(plotWidth / 90)), true).map((month) => ({ value: month, label: monthLabel(month) }));

  const label = payoff.paidOff
    ? `Kalan borç grafiği: ${formatMoney(payoff.totalDebt)} borç ${lastMonth} ayda sıfıra iniyor.`
    : `Kalan borç grafiği: ${formatMoney(payoff.totalDebt)} borç ${lastMonth} ay sonunda hâlâ ${formatMoney(series[series.length - 1].balance)}.`;

  return (
    <figure className="chart-figure">
      <LineChart
        points={series.map((p) => ({ x: p.month, y: p.balance }))}
        xDomain={[0, lastMonth]}
        yDomain={[0, yMax]}
        yTicks={yTicks}
        xTicks={xTicks}
        area
        height={200}
        marginLeft={Math.max(32, longestLabel * 7 + 14)}
        label={label}
        describe={(index) => describeBalance(series[index])}
        tooltip={(index) => <BalanceTooltip point={series[index]} />}
      />
      <figcaption className="chart-caption">
        <span>Yatay eksen ay, dikey eksen kalan borç (TL).</span>
      </figcaption>
    </figure>
  );
}
