// Pure helpers behind the dashboard's SVG charts: scales, ticks, nearest point, label thinning. No DOM, unit tested.
import { formatNumber } from "../../lib/format";

export type Domain = readonly [number, number];

// removes floating point noise (0.1 + 0.2 -> 0.3) so tick values print cleanly
function clean(value: number): number {
  return Number(value.toPrecision(12));
}

// maps a value from the domain to the range linearly; a zero-width domain maps everything to the middle of the range
export function scaleLinear(domain: Domain, range: Domain): (value: number) => number {
  const [d0, d1] = domain;
  const [r0, r1] = range;
  const span = d1 - d0;
  if (span === 0) {
    const middle = (r0 + r1) / 2;
    return () => middle;
  }
  return (value) => r0 + ((value - d0) / span) * (r1 - r0);
}

// a "nice" step for about `count` intervals over `span`: 1, 2, 2.5 or 5 times a power of ten.
// integer=true (months) never returns 2.5 or a step below 1
export function niceStep(span: number, count: number, integer = false): number {
  if (!(span > 0) || !(count > 0)) return 1;
  const raw = span / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  const residual = raw / magnitude;
  const factors = integer ? [1, 2, 5, 10] : [1, 2, 2.5, 5, 10];
  const factor = factors.find((f) => residual <= f + 1e-9) ?? 10;
  const step = clean(factor * magnitude);
  return integer ? Math.max(1, Math.round(step)) : step;
}

// ticks from 0 up to the first nice value >= max, e.g. max 30000 -> 0, 10000, 20000, 30000 (a value axis whose top
// tick is also the domain end, so the data never touches the frame)
export function zeroBasedTicks(max: number, count = 4): number[] {
  if (!(max > 0)) return [0];
  const step = niceStep(max, count);
  const steps = Math.ceil(max / step - 1e-9);
  return Array.from({ length: steps + 1 }, (_, i) => clean(i * step));
}

// multiples of a nice step that lie within [0, max] (an x axis that must not run past the data), always with 0
export function ticksWithin(max: number, count: number, integer = false): number[] {
  if (!(max > 0)) return [0];
  const step = niceStep(max, Math.max(1, count), integer);
  const ticks: number[] = [];
  for (let i = 0; clean(i * step) <= max + 1e-9; i += 1) ticks.push(clean(i * step));
  return ticks;
}

// index of the position closest to x (positions ascending); -1 for an empty list
export function nearestIndex(positions: readonly number[], x: number): number {
  let best = -1;
  let bestDistance = Number.POSITIVE_INFINITY;
  positions.forEach((position, index) => {
    const distance = Math.abs(position - x);
    if (distance < bestDistance) {
      best = index;
      bestDistance = distance;
    }
  });
  return best;
}

// which of `count` evenly spaced points get an axis label: all when they fit, otherwise about maxLabels of them
// spread evenly, always the first and the last
export function labelIndices(count: number, maxLabels: number): number[] {
  if (count <= 0) return [];
  if (count === 1) return [0];
  const limit = Math.max(2, Math.floor(maxLabels));
  if (count <= limit) return Array.from({ length: count }, (_, i) => i);
  const step = (count - 1) / (limit - 1);
  const indices = Array.from({ length: limit }, (_, i) => Math.round(i * step));
  return [...new Set(indices)];
}

// SVG path through the points ("M x y L x y ..."); empty string for no points
export function linePath(points: readonly { x: number; y: number }[]): string {
  return points.map((p, i) => `${i === 0 ? "M" : "L"}${round1(p.x)} ${round1(p.y)}`).join(" ");
}

// the line closed down to the baseline, for a soft area wash under it
export function areaPath(points: readonly { x: number; y: number }[], baseline: number): string {
  if (points.length === 0) return "";
  const first = points[0];
  const last = points[points.length - 1];
  return `${linePath(points)} L${round1(last.x)} ${round1(baseline)} L${round1(first.x)} ${round1(baseline)} Z`;
}

function round1(value: number): string {
  return String(Math.round(value * 10) / 10);
}

const COMPACT = new Intl.NumberFormat("tr-TR", { notation: "compact", maximumFractionDigits: 1 });

// amount axis tick: in full while the axis stays under 10.000 ("2.500"), compact once it reaches it ("30 B", "1,5 Mn")
export function axisAmountLabel(value: number, axisMax: number): string {
  return axisMax < 10_000 ? formatNumber(value) : COMPACT.format(value);
}
