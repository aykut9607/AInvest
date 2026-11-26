import { useEffect, useRef, useState } from "react";
import { assetLabel } from "../../lib/labels";
import { formatMoney, formatPercent } from "../../lib/format";
import type { PortfolioProposal } from "../../types/api";
import { allocationParts, labelFits, swatchFor, type AllocationPart } from "./proposal";

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState<number | null>(null);
  useEffect(() => {
    const element = ref.current;
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver((entries) => {
      const next = entries[0]?.contentRect.width;
      if (typeof next === "number") setWidth(Math.round(next));
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, []);
  return { ref, width };
}

const partText = (part: AllocationPart) => `${part.label}: ${formatPercent(part.percent)}, ${formatMoney(part.amount)}`;

// One whole split into its parts, read beside a table (dataviz "tall segmented bar"): blocks proportional to the
// service's percentages with 2 px surface gaps, the share printed inside a block only when it fits, every part's
// name, share and amount on hover and keyboard focus, and the table as the full, colour-independent twin.
export default function AllocationChart({
  allocations,
  monthlyAmount,
}: {
  allocations: PortfolioProposal["allocations"];
  monthlyAmount: number;
}) {
  const parts = allocationParts(allocations);
  const { ref, width } = useWidth<HTMLDivElement>();
  const [active, setActive] = useState<string | null>(null);
  const activePart = parts.find((p) => p.key === active) ?? null;

  if (allocations.length === 0) {
    return <p className="text-sm text-muted">Öneride dağılım yok.</p>;
  }

  return (
    <figure className="alloc">
      <div
        ref={ref}
        className="alloc-bar"
        role="list"
        aria-label="Varlık dağılımı çubuğu"
        onPointerLeave={() => setActive(null)}
      >
        {parts.map((part) => {
          const label = formatPercent(part.percent);
          return (
            <div
              key={part.key}
              role="listitem"
              tabIndex={0}
              className={`alloc-part${active === part.key ? " is-active" : ""}`}
              style={{ flexGrow: part.percent, background: part.color, color: part.ink }}
              aria-label={partText(part)}
              onPointerEnter={() => setActive(part.key)}
              onFocus={() => setActive(part.key)}
              onBlur={() => setActive((current) => (current === part.key ? null : current))}
            >
              {labelFits(part.percent, width, label) ? <span aria-hidden="true">{label}</span> : null}
            </div>
          );
        })}
      </div>
      <p className="alloc-readout" aria-live="polite">
        {activePart ? (
          <>
            <strong className="tabular">{formatPercent(activePart.percent)}</strong>{" "}
            <span className="tabular">{formatMoney(activePart.amount)}</span>{" "}
            <span className="text-secondary">{activePart.label}</span>
          </>
        ) : (
          <span className="text-muted">Bir parçanın üzerine gel ya da sekme tuşuyla seç.</span>
        )}
      </p>
      <figcaption className="visually-hidden">Varlık dağılımı; ayrıntılar aşağıdaki tabloda.</figcaption>
      <div className="table-wrap">
        <table className="table">
          <caption className="visually-hidden">Varlık dağılımı tablosu</caption>
          <thead>
            <tr>
              <th scope="col">Varlık</th>
              <th scope="col" className="num">
                Pay
              </th>
              <th scope="col" className="num">
                Aylık tutar
              </th>
            </tr>
          </thead>
          <tbody>
            {allocations.map((allocation) => (
              <tr key={allocation.asset}>
                <th scope="row">
                  <span className="alloc-asset">
                    <span className="alloc-swatch" style={{ background: swatchFor(parts, allocation.asset) }} aria-hidden="true" />
                    {assetLabel(allocation.asset)}
                  </span>
                </th>
                <td className="num">{formatPercent(allocation.percent)}</td>
                <td className="num">{formatMoney(allocation.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="text-xs text-muted">
        Tutarlar aylık yatırılabilir {formatMoney(monthlyAmount)} içindeki paylardır; Portföy servisi hesaplar.
      </p>
    </figure>
  );
}
