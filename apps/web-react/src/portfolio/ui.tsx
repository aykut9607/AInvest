import type { ReactNode } from "react";

export function Card({ title, note, children, className = "" }: { title?: ReactNode; note?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`pf-card ${className}`}>
      {title && <h2>{title}</h2>}
      {note && <p className="pf-note">{note}</p>}
      {children}
    </section>
  );
}

export function Banner({ kind = "info", title, children }: { kind?: "info" | "success" | "warning" | "danger"; title: string; children?: ReactNode }) {
  return (
    <div className={`pf-banner pf-${kind}`} role={kind === "danger" ? "alert" : "status"}>
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v5M12 8h.01" strokeLinecap="round" />
      </svg>
      <div>
        <strong>{title}</strong>
        {children && <div>{children}</div>}
      </div>
    </div>
  );
}

export function Pill({ tone = "neutral", children }: { tone?: "neutral" | "good" | "warn" | "bad" | "blue"; children: ReactNode }) {
  return <span className={`pf-pill pf-tone-${tone}`}>{children}</span>;
}

export function Button({ children, onClick, busy = false, disabled = false, kind = "primary", type = "button" }: { children: ReactNode; onClick?: () => void; busy?: boolean; disabled?: boolean; kind?: "primary" | "quiet"; type?: "button" | "submit" }) {
  return (
    <button type={type} className={`pf-button pf-${kind}`} onClick={onClick} disabled={busy || disabled} aria-busy={busy}>
      {busy && <span className="pf-spinner" aria-hidden="true" />}
      {children}
    </button>
  );
}

export function Tile({ label, value, tone = "", hint }: { label: string; value: ReactNode; tone?: "" | "good" | "bad"; hint?: string }) {
  return (
    <div className="pf-tile">
      <span>{label}</span>
      <b className={tone ? `pf-text-${tone}` : ""}>{value}</b>
      {hint && <small>{hint}</small>}
    </div>
  );
}

export function Loading({ text = "Yükleniyor…" }: { text?: string }) {
  return (
    <p className="pf-loading" role="status">
      <span className="pf-spinner" aria-hidden="true" /> {text}
    </p>
  );
}

// a card that is chosen like a radio button
export function Choice({ selected, locked = false, onClick, tag, title, children, badge }: { selected: boolean; locked?: boolean; onClick: () => void; tag?: string; title: string; children: ReactNode; badge?: ReactNode }) {
  return (
    <button type="button" role="radio" aria-checked={selected} aria-disabled={locked} className={`pf-choice${selected ? " pf-on" : ""}${locked ? " pf-locked" : ""}`} onClick={locked ? undefined : onClick}>
      <span className="pf-choice-top">
        {tag && <span className="pf-number">{tag}</span>}
        {badge}
      </span>
      <strong>
        {locked && (
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" aria-hidden="true">
            <rect x="5" y="11" width="14" height="9" rx="2" />
            <path d="M8 11V8a4 4 0 0 1 8 0v3" />
          </svg>
        )}
        {title}
      </strong>
      <span className="pf-choice-text">{children}</span>
    </button>
  );
}

// several can be on at the same time
export function Chips({ items, value, onToggle, disabled = [], label }: { items: { code: string; label: string }[]; value: string[]; onToggle: (code: string) => void; disabled?: string[]; label: string }) {
  return (
    <div className="pf-chips" role="group" aria-label={label}>
      {items.map((x) => (
        <button key={x.code} type="button" className={`pf-chip${value.includes(x.code) ? " pf-on" : ""}`} aria-pressed={value.includes(x.code)} disabled={disabled.includes(x.code)} onClick={() => onToggle(x.code)}>
          {x.label}
        </button>
      ))}
    </div>
  );
}

export function Tabs<T extends string>({ tabs, value, onChange }: { tabs: { id: T; label: string; count?: number }[]; value: T; onChange: (id: T) => void }) {
  return (
    <div className="pf-tabs" role="tablist">
      {tabs.map((t) => (
        <button key={t.id} type="button" role="tab" aria-selected={t.id === value} className={t.id === value ? "pf-on" : ""} onClick={() => onChange(t.id)}>
          {t.label}
          {t.count !== undefined && <span>{t.count}</span>}
        </button>
      ))}
    </div>
  );
}

export function Empty({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="pf-empty">
      <strong>{title}</strong>
      {children && <p>{children}</p>}
    </div>
  );
}
