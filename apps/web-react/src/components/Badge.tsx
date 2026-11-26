import type { ReactNode } from "react";

export type BadgeTone = "neutral" | "info" | "good" | "warning" | "serious" | "critical";

export interface BadgeProps {
  tone?: BadgeTone;
  // coloured dot before the text (status badges: the colour never stands alone, the text says it too)
  dot?: boolean;
  size?: "md" | "lg";
  title?: string;
  children: ReactNode;
}

export default function Badge({ tone = "neutral", dot = false, size = "md", title, children }: BadgeProps) {
  const classes = ["badge", tone === "neutral" ? "" : `badge-${tone}`, dot ? "badge-dot" : "", size === "lg" ? "badge-lg" : ""]
    .filter(Boolean)
    .join(" ");
  return (
    <span className={classes} title={title}>
      {children}
    </span>
  );
}
