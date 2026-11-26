import { useState, type KeyboardEvent, type PointerEvent, type ReactNode } from "react";
import { areaPath, linePath, nearestIndex, scaleLinear, type Domain } from "./chartMath";
import { useElementWidth } from "./hooks";

export interface ChartPoint {
  x: number;
  y: number;
}

export interface ChartTick {
  value: number;
  label: string;
}

// a faint horizontal background band between two y values (the IQ segments), with a label in the right gutter
export interface ChartBand {
  from: number;
  to: number;
  tone: "low" | "medium" | "high";
  label: string;
}

export interface LineChartProps {
  // ascending by x
  points: ChartPoint[];
  xDomain: Domain;
  yDomain: Domain;
  yTicks: ChartTick[];
  // x ticks for the plot width in pixels (wider plot -> more labels)
  xTicks: (plotWidth: number) => ChartTick[];
  bands?: ChartBand[];
  // a soft wash under the line (single-series area chart)
  area?: boolean;
  // a marker on every point (few points); otherwise only the active point gets one
  markers?: boolean;
  // value printed above the last point
  endLabel?: string;
  height?: number;
  // room for the y tick labels
  marginLeft?: number;
  // accessible name: what the chart shows, in one sentence
  label: string;
  // screen reader text for the point under the pointer / keyboard
  describe: (index: number) => string;
  tooltip: (index: number) => ReactNode;
  markerTestId?: string;
}

const MARGIN_TOP = 24;
const MARGIN_BOTTOM = 28;
const MARGIN_RIGHT = 12;
// right gutter for the band labels, only drawn when the chart is wide enough
const BAND_GUTTER = 64;
const BAND_LABELS_MIN_WIDTH = 420;
// keeps the first and last markers off the plot edges
const INSET = 12;
// before the first measurement (and on the server); CSS scales it down to the container until then
const FALLBACK_WIDTH = 640;

// Single-series line chart in real pixels: hairline grid, 2px line, >= 8px markers with a surface ring, crosshair
// that snaps to the nearest point, one tooltip, keyboard navigation (arrows, Home/End, PageUp/PageDown, Esc).
// The tooltip only enhances: every value is also in the table view next to the chart.
export default function LineChart({
  points,
  xDomain,
  yDomain,
  yTicks,
  xTicks,
  bands,
  area = false,
  markers = false,
  endLabel,
  height = 240,
  marginLeft = 36,
  label,
  describe,
  tooltip,
  markerTestId,
}: LineChartProps) {
  const [containerRef, width] = useElementWidth<HTMLDivElement>(FALLBACK_WIDTH);
  const [active, setActive] = useState<number | null>(null);

  const showBandLabels = Boolean(bands?.length) && width >= BAND_LABELS_MIN_WIDTH;
  const left = marginLeft;
  const right = Math.max(left + 2 * INSET + 1, width - (showBandLabels ? BAND_GUTTER : MARGIN_RIGHT));
  const top = MARGIN_TOP;
  const bottom = height - MARGIN_BOTTOM;
  const x = scaleLinear(xDomain, [left + INSET, right - INSET]);
  const y = scaleLinear(yDomain, [bottom, top]);

  const pixels = points.map((p) => ({ x: x(p.x), y: y(p.y) }));
  const xs = pixels.map((p) => p.x);
  const current = active !== null && active < points.length ? active : null;
  const last = pixels.length > 0 ? pixels[pixels.length - 1] : null;
  const lastIndex = points.length - 1;

  const handlePointer = (event: PointerEvent<HTMLDivElement>) => {
    if (points.length === 0) return;
    const rect = event.currentTarget.getBoundingClientRect();
    setActive(nearestIndex(xs, event.clientX - rect.left));
  };

  const handlePointerLeave = (event: PointerEvent<HTMLDivElement>) => {
    // keep the readout while the plot has keyboard focus
    if (document.activeElement !== event.currentTarget) setActive(null);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (points.length === 0) return;
    const page = Math.max(1, Math.round(points.length / 10));
    let next: number;
    switch (event.key) {
      case "ArrowRight":
      case "ArrowUp":
        next = current === null ? 0 : Math.min(lastIndex, current + 1);
        break;
      case "ArrowLeft":
      case "ArrowDown":
        next = current === null ? lastIndex : Math.max(0, current - 1);
        break;
      case "PageUp":
        next = Math.min(lastIndex, (current ?? 0) + page);
        break;
      case "PageDown":
        next = Math.max(0, (current ?? lastIndex) - page);
        break;
      case "Home":
        next = 0;
        break;
      case "End":
        next = lastIndex;
        break;
      case "Escape":
        setActive(null);
        return;
      default:
        return;
    }
    event.preventDefault();
    setActive(next);
  };

  const tickAnchor = (px: number): "start" | "middle" | "end" => {
    if (px < left + 36) return "start";
    if (px > right - 36) return "end";
    return "middle";
  };

  const tooltipSide = current !== null && xs[current] > width / 2 ? "left" : "right";

  return (
    <div className="chart" ref={containerRef}>
      <div
        className="chart-plot"
        tabIndex={0}
        role="group"
        aria-label={`${label} Noktalar arasında ok tuşlarıyla gezinebilirsin.`}
        onPointerMove={handlePointer}
        onPointerDown={handlePointer}
        onPointerLeave={handlePointerLeave}
        onKeyDown={handleKeyDown}
        onFocus={() => setActive((previous) => previous ?? (points.length > 0 ? lastIndex : null))}
        onBlur={() => setActive(null)}
      >
        <svg
          className="chart-svg"
          width={width}
          height={height}
          viewBox={`0 0 ${width} ${height}`}
          aria-hidden="true"
          focusable="false"
        >
          {bands?.map((band) => {
            const y0 = y(band.to);
            const y1 = y(band.from);
            return (
              <g key={band.tone}>
                <rect x={left} y={y0} width={right - left} height={Math.max(0, y1 - y0)} className={`chart-band chart-band-${band.tone}`} />
                {showBandLabels ? (
                  <text x={right + 8} y={(y0 + y1) / 2} dominantBaseline="middle" className="chart-band-label">
                    {band.label}
                  </text>
                ) : null}
              </g>
            );
          })}

          {yTicks.map((tick) => (
            <g key={`y-${tick.value}`}>
              <line
                x1={left}
                x2={right}
                y1={y(tick.value)}
                y2={y(tick.value)}
                className={tick.value === yDomain[0] ? "chart-axis" : "chart-grid"}
              />
              <text x={left - 8} y={y(tick.value)} textAnchor="end" dominantBaseline="middle" className="chart-tick">
                {tick.label}
              </text>
            </g>
          ))}

          {xTicks(right - left).map((tick) => {
            const px = x(tick.value);
            return (
              <text key={`x-${tick.value}`} x={px} y={bottom + 18} textAnchor={tickAnchor(px)} className="chart-tick">
                {tick.label}
              </text>
            );
          })}

          {area && pixels.length > 1 ? <path d={areaPath(pixels, bottom)} className="chart-area" /> : null}
          {pixels.length > 1 ? <path d={linePath(pixels)} className="chart-line" /> : null}

          {current !== null ? <line x1={xs[current]} x2={xs[current]} y1={top} y2={bottom} className="chart-crosshair" /> : null}

          {markers
            ? pixels.map((p, index) => (
                <circle
                  key={index}
                  cx={p.x}
                  cy={p.y}
                  r={index === current ? 6.5 : 5}
                  className="chart-marker"
                  data-testid={markerTestId}
                />
              ))
            : null}
          {!markers && current !== null ? <circle cx={pixels[current].x} cy={pixels[current].y} r={6} className="chart-marker" /> : null}

          {endLabel && last ? (
            <text x={last.x} y={last.y - 12} textAnchor={last.x > right - 24 ? "end" : "middle"} className="chart-end-label">
              {endLabel}
            </text>
          ) : null}
        </svg>

        {current !== null ? (
          <div className="chart-tooltip" data-side={tooltipSide} style={{ left: xs[current], top }} aria-hidden="true">
            {tooltip(current)}
          </div>
        ) : null}
      </div>
      <p className="visually-hidden" aria-live="polite">
        {current !== null ? describe(current) : ""}
      </p>
    </div>
  );
}
