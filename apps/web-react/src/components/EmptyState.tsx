import type { ReactNode } from "react";

export interface EmptyStateProps {
  title: string;
  description?: ReactNode;
  // e.g. a <Link className="btn btn-primary"> to the page that creates the missing data
  action?: ReactNode;
  icon?: ReactNode;
}

export default function EmptyState({ title, description, action, icon }: EmptyStateProps) {
  return (
    <div className="empty-state">
      <div className="empty-state-icon" aria-hidden="true">
        {icon ?? (
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
            <path d="M4 19V5M4 19h16M8 15l3-4 3 2 4-6" />
          </svg>
        )}
      </div>
      <h2 className="empty-state-title">{title}</h2>
      {description ? <p className="empty-state-description">{description}</p> : null}
      {action ? <div className="cluster">{action}</div> : null}
    </div>
  );
}
