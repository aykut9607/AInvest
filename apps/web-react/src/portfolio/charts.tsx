import { useState, type PointerEvent } from "react";
import { day, percent, price, usd, zone } from "./text";
import type { Trade } from "./types";

// fixed order of hues, validated for the dark surface; an asset keeps its place, never its rank
const HUES = ["#3987e5", "#d95926", "#199e70", "#c98500", "#d55181", "#9085e9", "#e66767", "#6b9c2f"];
const hue = (i: number) => HUES[i % HUES.length];

export function Distribution({ items }: { items: { code: string; label: string; percent: number; amount: string; once: string }[] }) {
  const [on, setOn] = useState<string | null>(null);
  const active = items.find((x) => x.code === on) ?? null;
  return (
    <div>
      <div className="pf-stack" role="img" aria-label={items.map((x) => `${x.label} ${percent(x.percent, 1)}`).join(", ")} onPointerLeave={() => setOn(null)}>
        {items.map((x, i) => (
          <button
            key={x.code}
            type="button"
            style={{ width: `${x.percent}%`, background: hue(i) }}
            className={on && on !== x.code ? "pf-dim" : ""}
            aria-label={`${x.label} ${percent(x.percent, 1)}`}
            onPointerEnter={() => setOn(x.code)}
            onFocus={() => setOn(x.code)}
            onBlur={() => setOn(null)}
          >
            {x.percent >= 9 ? percent(x.percent, 0) : ""}
          </button>
        ))}
      </div>
      <p className="pf-note" aria-live="polite">
        {active ? `${active.label}: ${percent(active.percent, 2)} · aylık ${active.amount} · tek seferlik ${active.once}` : "Bir parçanın üzerine gel ya da sekme tuşuyla seç."}
      </p>
      <div className="pf-scroll">
        <table className="pf-table">
          <thead>
            <tr>
              <th>Varlık</th>
              <th>Pay</th>
              <th>Her ay</th>
              <th>Tek seferlik</th>
            </tr>
          </thead>
          <tbody>
            {items.map((x, i) => (
              <tr key={x.code} className={on === x.code ? "pf-row-on" : ""} onPointerEnter={() => setOn(x.code)} onPointerLeave={() => setOn(null)}>
                <td>
                  <i className="pf-dot" style={{ background: hue(i) }} /> {x.label}
                </td>
                <td>{percent(x.percent, 2)}</td>
                <td>{x.amount}</td>
                <td>{x.once}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function BalanceChart({ points, start }: { points: { time: number; balance: number }[]; start: number }) {
  const [at, setAt] = useState<number | null>(null);
  if (points.length < 2) return null;
  const W = 1000, H = 240, left = 62, right = 16, bottom = 28;
  const values = [start, ...points.map((p) => p.balance)];
  const low = Math.min(...values), high = Math.max(...values), pad = Math.max(8, (high - low) * 0.08);
  const x = (i: number) => left + (i / (values.length - 1)) * (W - left - right);
  const y = (v: number) => 8 + ((high + pad - v) / (high - low + 2 * pad)) * (H - bottom - 8);
  const step = [5, 10, 20, 50, 100, 200, 500].find((s) => (high - low + 2 * pad) / s <= 6) ?? 1000;
  const lines: number[] = [];
  for (let v = Math.ceil((low - pad) / step) * step; v <= high + pad; v += step) lines.push(v);
  const ticks = [0, Math.floor((points.length - 1) / 3), Math.floor((2 * (points.length - 1)) / 3), points.length - 1];
  const move = (e: PointerEvent<SVGSVGElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.round((((e.clientX - box.left) / box.width) * W - left) / (W - left - right) * (values.length - 1));
    setAt(Math.max(1, Math.min(values.length - 1, i)));
  };
  const point = at === null ? null : points[at - 1];
  return (
    <figure className="pf-figure">
      <svg viewBox={`0 0 ${W} ${H}`} role="img" aria-label={`Kasa ${usd(start)} ile başladı, ${usd(values[values.length - 1])} ile bitti`} onPointerMove={move} onPointerLeave={() => setAt(null)}>
        {lines.map((v) => (
          <g key={v}>
            <line x1={left} x2={W - right} y1={y(v)} y2={y(v)} className={v === start ? "pf-axis" : "pf-grid"} />
            <text x={left - 8} y={y(v) + 4} textAnchor="end">
              {v}
            </text>
          </g>
        ))}
        {ticks.map((i, k) => (
          <text key={i} x={x(i + 1)} y={H - 6} textAnchor={k === 0 ? "start" : k === 3 ? "end" : "middle"}>
            {day(points[i].time)}
          </text>
        ))}
        <polyline points={values.map((v, i) => `${x(i)},${y(v)}`).join(" ")} className="pf-line" />
        {point && at !== null && (
          <>
            <line x1={x(at)} x2={x(at)} y1={8} y2={H - bottom} className="pf-axis" strokeDasharray="3 4" />
            <circle cx={x(at)} cy={y(point.balance)} r="5" className="pf-mark" />
          </>
        )}
      </svg>
      <figcaption>{point ? `${day(point.time)} · kasa ${usd(point.balance)}` : "Her nokta kapanan bir işlem. Üzerine gel."}</figcaption>
    </figure>
  );
}

// stop, entry and targets on one price line; what was reached is filled
export function PlanLine({ trade }: { trade: Trade }) {
  const W = 1000, side = trade.direction === "LONG" ? 1 : -1;
  const marks = [{ zone: "STOP", price: trade.stop, units: 0 }, { zone: "ENTRY", price: trade.entry, units: 0 }, ...trade.steps];
  const all = marks.map((m) => m.price);
  const low = Math.min(...all), high = Math.max(...all);
  const x = (p: number) => {
    const share = (p - low) / (high - low || 1);
    return 40 + (side === 1 ? share : 1 - share) * (W - 80);
  };
  const taken = new Set(trade.takeProfits.map((f) => f.zone));
  const best = trade.entry * (1 + (side * trade.maxProfit.percent) / 100);
  const bestInside = Math.max(low, Math.min(high, best));
  // neighbours closer than a label are put on different rows
  const title = (m: { zone: string; units: number }) => (m.zone === "ENTRY" ? "Giriş" : zone(m.zone)) + (m.units ? ` · ${percent(m.units)}` : "");
  const anchorOf = (px: number) => (px < 80 ? "start" : px > W - 80 ? "end" : "middle");
  const rows: number[] = [];
  const last = [-999, -999, -999, -999];
  for (const m of [...marks].sort((a, b) => x(a.price) - x(b.price))) {
    const px = x(m.price), wide = title(m).length * 7.4, anchor = anchorOf(px);
    const begin = anchor === "start" ? px : anchor === "end" ? px - wide : px - wide / 2;
    const row = Math.max(0, last.findIndex((end) => begin - end > 10));
    last[row] = begin + wide;
    rows[marks.indexOf(m)] = row;
  }
  return (
    <svg viewBox={`0 0 ${W} 190`} className="pf-plan" role="img" aria-label="İşlem planı">
      <line x1={x(trade.stop)} x2={x(trade.entry)} y1="50" y2="50" className="pf-plan-risk" />
      <line x1={x(trade.entry)} x2={x(trade.steps[trade.steps.length - 1].price)} y1="50" y2="50" className="pf-plan-reward" />
      <line x1={x(trade.entry)} x2={x(bestInside)} y1="50" y2="50" className="pf-plan-best" />
      {marks.map((m, i) => {
        const kind = m.zone === "STOP" ? "bad" : m.zone === "ENTRY" ? "entry" : "good";
        const done = taken.has(m.zone) || (m.zone === "STOP" && trade.stopped?.zone === "STOP");
        const px = x(m.price), top = 84 + rows[i] * 34;
        const anchor = anchorOf(px);
        return (
          <g key={m.zone} className={`pf-plan-${kind}`}>
            <line x1={px} x2={px} y1="56" y2={top - 14} className="pf-plan-stem" />
            <circle cx={px} cy="50" r="7" className={done || m.zone === "ENTRY" ? "pf-full" : "pf-hollow"} />
            <text x={px} y={top} textAnchor={anchor} className="pf-plan-name">
              {title(m)}
            </text>
            <text x={px} y={top + 15} textAnchor={anchor}>
              {price(m.price)}
            </text>
          </g>
        );
      })}
      <text x={x(bestInside)} y="28" textAnchor={anchorOf(x(bestInside))} className="pf-plan-top">
        en iyi {percent(trade.maxProfit.roiPercent)}
      </text>
    </svg>
  );
}
