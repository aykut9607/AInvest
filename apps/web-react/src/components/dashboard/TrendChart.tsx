import { formatDateTime } from "../../lib/format";
import { SEGMENT_LABELS, SEGMENT_RANGES } from "../../lib/labels";
import type { IqTrendPoint, Segment } from "../../types/api";
import { labelIndices } from "./chartMath";
import { describeTrendPoint, formatAverage, formatChange, trendAxisLabels, trendSummary } from "./dashboardData";
import LineChart, { type ChartBand, type ChartTick } from "./LineChart";

// band edges sit between the integer scores: 40 is still LOW, 41 already MEDIUM
const BANDS: ChartBand[] = [
  { from: 0, to: 40.5, tone: "low", label: SEGMENT_LABELS.LOW },
  { from: 40.5, to: 70.5, tone: "medium", label: SEGMENT_LABELS.MEDIUM },
  { from: 70.5, to: 100, tone: "high", label: SEGMENT_LABELS.HIGH },
];

// ticks at the segment edges, so the grid itself says where a segment starts
const Y_TICKS: ChartTick[] = [0, 40, 70, 100].map((value) => ({ value, label: String(value) }));

const SEGMENT_TONE: Record<Segment, string> = { LOW: "low", MEDIUM: "medium", HIGH: "high" };

function TrendTooltip({ point }: { point: IqTrendPoint }) {
  return (
    <>
      <p className="chart-tooltip-title">{formatDateTime(point.calculatedAt)}</p>
      <p className="chart-tooltip-value">
        <span className="chart-key-line" aria-hidden="true" />
        <strong>{point.score}</strong>
        <span className="chart-tooltip-name">{`skor · ${SEGMENT_LABELS[point.segment] ?? point.segment}`}</span>
      </p>
      <dl className="chart-tooltip-rows">
        <dt>Değişim</dt>
        <dd>{formatChange(point.scoreChange)}</dd>
        <dt>3'lü ort.</dt>
        <dd>{formatAverage(point.movingAverage3)}</dd>
      </dl>
    </>
  );
}

// Financial IQ history: one point per calculation, evenly spaced in calculation order (the service's change and
// 3-point average are per calculation too), y fixed to 0-100 over the three segment bands.
export default function TrendChart({ points }: { points: IqTrendPoint[] }) {
  const axisLabels = trendAxisLabels(points);
  const data = points.map((point, index) => ({ x: index, y: point.score }));
  const last = points[points.length - 1];

  const xTicks = (plotWidth: number): ChartTick[] =>
    labelIndices(points.length, Math.floor(plotWidth / 84)).map((index) => ({ value: index, label: axisLabels[index] }));

  return (
    <figure className="chart-figure">
      <LineChart
        points={data}
        xDomain={[0, Math.max(1, points.length - 1)]}
        yDomain={[0, 100]}
        yTicks={Y_TICKS}
        xTicks={xTicks}
        bands={BANDS}
        markers
        endLabel={last ? String(last.score) : undefined}
        height={240}
        marginLeft={32}
        label={trendSummary(points)}
        describe={(index) => describeTrendPoint(points[index])}
        tooltip={(index) => <TrendTooltip point={points[index]} />}
        markerTestId="trend-point"
      />
      <figcaption className="chart-caption">
        <ul className="chart-band-key" aria-label="Segment aralıkları">
          {(Object.keys(SEGMENT_TONE) as Segment[]).map((segment) => (
            <li key={segment}>
              <span className={`chart-band-swatch chart-band-${SEGMENT_TONE[segment]}`} aria-hidden="true" />
              {`${SEGMENT_LABELS[segment]} ${SEGMENT_RANGES[segment]}`}
            </li>
          ))}
        </ul>
        <span>Her nokta bir hesaplama; noktalar hesaplama sırasına göre eşit aralıklı.</span>
      </figcaption>
    </figure>
  );
}
