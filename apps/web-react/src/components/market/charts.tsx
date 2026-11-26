import { useState, type PointerEvent } from "react";
import type { MarketTrade } from "../../types/market";
import { day, percent, price, usd, zone } from "./text";

// Ported from Aykut's src/portfolio/charts.tsx; colours come from tokens.css (market.css).

// the account after every closed trade; hover shows the date and the balance
export function BalanceChart({ points, start }: { points: { time: number; balance: number }[]; start: number }) {
  const [at, setAt] = useState<number | null>(null);
  if (points.length < 2) return null;
  const W = 1000,
    H = 240,
    left = 62,
    right = 16,
    bottom = 28;
  const values = [start, ...points.map((p) => p.balance)];
  const low = Math.min(...values),
    high = Math.max(...values),
    pad = Math.max(8, (high - low) * 0.08);
  const x = (i: number) => left + (i / (values.length - 1)) * (W - left - right);
  const y = (v: number) => 8 + ((high + pad - v) / (high - low + 2 * pad)) * (H - bottom - 8);
  const step = [5, 10, 20, 50, 100, 200, 500].find((s) => (high - low + 2 * pad) / s <= 6) ?? 1000;
  const lines: number[] = [];
  for (let v = Math.ceil((low - pad) / step) * step; v <= high + pad; v += step) lines.push(v);
  const ticks = [...new Set([0, Math.floor((points.length - 1) / 3), Math.floor((2 * (points.length - 1)) / 3), points.length - 1])];
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((((e.clientX - box.left) / box.width) * W - left) / (W - left - right)) * (values.length - 1));
    setAt(Math.max(1, Math.min(values.length - 1, i)));
  };
  const point = at === null ? null : points[at - 1];
  return (
    <figure className="market-figure">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label={`Kasa ${usd(start)} ile başladı, ${usd(values[values.length - 1])} ile bitti`}
        onPointerMove={move}
        onPointerLeave={() => setAt(null)}
      >
        {lines.map((v) => (
          <g key={v}>
            <line x1={left} x2={W - right} y1={y(v)} y2={y(v)} className={v === start ? "market-axis" : "market-grid"} />
            <text x={left - 8} y={y(v) + 4} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {ticks.map((i, k) => (
          <text key={i} x={x(i + 1)} y={H - 6} textAnchor={k === 0 ? "start" : k === ticks.length - 1 ? "end" : "middle"}>
            {day(points[i].time)}
          </text>
        ))}
        <polyline points={values.map((v, i) => `${x(i)},${y(v)}`).join(" ")} className="market-line" />
        {point && at !== null && (
          <>
            <line x1={x(at)} x2={x(at)} y1={8} y2={H - bottom} className="market-axis" strokeDasharray="3 4" />
            <circle cx={x(at)} cy={y(point.balance)} r="5" className="market-mark" />
          </>
        )}
      </svg>
      <figcaption>{point ? `${day(point.time)} · kasa ${usd(point.balance)}` : "Her nokta kapanan bir işlem. Üzerine gel."}</figcaption>
    </figure>
  );
}

// stop, entry and targets on one price line; what was reached is filled
export function PlanLine({ trade }: { trade: MarketTrade }) {
  if (!trade.steps.length) return null;
  const W = 1000,
    side = trade.direction === "LONG" ? 1 : -1;
  const marks = [{ zone: "STOP", price: trade.stop, units: 0 }, { zone: "ENTRY", price: trade.entry, units: 0 }, ...trade.steps];
  const all = marks.map((m) => m.price);
  const low = Math.min(...all),
    high = Math.max(...all);
  const x = (p: number) => {
    const share = (p - low) / (high - low || 1);
    return 40 + (side === 1 ? share : 1 - share) * (W - 80);
  };
  const taken = new Set(trade.takeProfits.map((f) => f.zone));
  const best = trade.entry * (1 + (side * trade.maxProfit.percent) / 100);
  const bestInside = Math.max(low, Math.min(high, best));
  const title = (m: { zone: string; units: number }) => zone(m.zone) + (m.units ? ` · ${percent(m.units)}` : "");
  const anchorOf = (px: number) => (px < 80 ? "start" : px > W - 80 ? "end" : "middle");
  // neighbours closer than a label are put on different rows
  const rows: number[] = [];
  const last = [-999, -999, -999, -999];
  for (const m of [...marks].sort((a, b) => x(a.price) - x(b.price))) {
    const px = x(m.price),
      wide = title(m).length * 7.4,
      anchor = anchorOf(px);
    const begin = anchor === "start" ? px : anchor === "end" ? px - wide : px - wide / 2;
    const row = Math.max(0, last.findIndex((end) => begin - end > 10));
    last[row] = begin + wide;
    rows[marks.indexOf(m)] = row;
  }
  return (
    <svg viewBox={`0 0 ${W} 190`} className="market-plan" role="img" aria-label="İşlem planı">
      <line x1={x(trade.stop)} x2={x(trade.entry)} y1="50" y2="50" className="market-plan-risk" />
      <line x1={x(trade.entry)} x2={x(trade.steps[trade.steps.length - 1].price)} y1="50" y2="50" className="market-plan-reward" />
      <line x1={x(trade.entry)} x2={x(bestInside)} y1="50" y2="50" className="market-plan-best" />
      {marks.map((m, i) => {
        const kind = m.zone === "STOP" ? "bad" : m.zone === "ENTRY" ? "entry" : "good";
        const done = taken.has(m.zone) || (m.zone === "STOP" && trade.stopped?.zone === "STOP");
        const px = x(m.price),
          top = 84 + rows[i] * 34;
        const anchor = anchorOf(px);
        return (
          <g key={m.zone} className={`market-plan-${kind}`}>
            <line x1={px} x2={px} y1="56" y2={top - 14} className="market-plan-stem" />
            <circle cx={px} cy="50" r="7" className={done || m.zone === "ENTRY" ? "market-full" : "market-hollow"} />
            <text x={px} y={top} textAnchor={anchor} className="market-plan-name">
              {title(m)}
            </text>
            <text x={px} y={top + 15} textAnchor={anchor}>
              {price(m.price)}
            </text>
          </g>
        );
      })}
      <text x={x(bestInside)} y="28" textAnchor={anchorOf(x(bestInside))} className="market-plan-top">
        en iyi {percent(trade.maxProfit.roiPercent)}
      </text>
    </svg>
  );
}
