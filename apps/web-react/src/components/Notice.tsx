import type { ReactNode } from "react";

export interface NoticeProps {
  tone?: "info" | "good" | "warning" | "error";
  title?: string;
  children: ReactNode;
}

// non-error message strip (info, success, warning); errors use ErrorBox
export default function Notice({ tone = "info", title, children }: NoticeProps) {
  const toneClass = tone === "info" ? "" : `notice-${tone}`;
  return (
    <div className={`notice ${toneClass}`.trim()} role={tone === "error" ? "alert" : "status"}>
      <svg className="notice-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 11v6M12 7.5v.5" strokeLinecap="round" />
      </svg>
      <div className="notice-body">
        {title ? <p className="notice-title">{title}</p> : null}
        <div>{children}</div>
      </div>
    </div>
  );
}
