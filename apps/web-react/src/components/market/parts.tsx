import type { ReactNode } from "react";
import type { MarketCategory } from "../../types/market";
import { plain, rule } from "./text";

// small building blocks of the 4.4 screens (Ahmet's shared Card/Badge/EmptyState cover the rest)

export function Stat({ label, value, tone, hint }: { label: string; value: ReactNode; tone?: "good" | "bad"; hint?: string }) {
  return (
    <div className="market-stat">
      <span>{label}</span>
      <b className={tone ? `market-text-${tone}` : undefined}>{value}</b>
      {hint ? <small>{hint}</small> : null}
    </div>
  );
}

export function Tabs<T extends string>({
  label,
  tabs,
  value,
  onChange,
}: {
  label: string;
  tabs: { id: T; label: string; count?: number }[];
  value: T;
  onChange: (id: T) => void;
}) {
  return (
    <div className="market-tabs" role="tablist" aria-label={label}>
      {tabs.map((t) => (
        <button
          key={t.id}
          type="button"
          role="tab"
          aria-selected={t.id === value}
          className={t.id === value ? "is-active" : undefined}
          onClick={() => onChange(t.id)}
        >
          {t.label}
          {t.count !== undefined ? <span className="market-tab-count">{t.count}</span> : null}
        </button>
      ))}
    </div>
  );
}

// why a trigger scored what it scored: one bar per category
export function ScoreBars({ categories, total }: { categories: Record<string, MarketCategory>; total: number }) {
  return (
    <div className="market-bars">
      {Object.entries(categories).map(([name, c]) => (
        <div key={name}>
          <span>
            {name}
            <small>
              {rule(c.rule)} · {c.frame}
              {c.also?.length ? ` · ${c.also.join(", ")} de destekliyor` : ""}
            </small>
          </span>
          <i>
            <b style={{ width: `${Math.min(100, (c.points / Math.max(total, 1)) * 100)}%` }} />
          </i>
          <em>{plain(c.points)}</em>
        </div>
      ))}
      <div className="market-bars-total">
        <span>Toplam puan</span>
        <i />
        <em>{plain(total)}</em>
      </div>
    </div>
  );
}
