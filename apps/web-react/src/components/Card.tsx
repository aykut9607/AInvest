import { useId, type ReactNode } from "react";

export interface CardProps {
  title?: ReactNode;
  subtitle?: ReactNode;
  // buttons or badges on the right of the title
  actions?: ReactNode;
  footer?: ReactNode;
  // "muted" = flat background for secondary content
  tone?: "default" | "muted";
  as?: "section" | "div" | "article" | "aside";
  // heading element of the title (default h2; h1 when the card is the page itself, e.g. sign-in)
  headingLevel?: 1 | 2 | 3;
  className?: string;
  children?: ReactNode;
}

export default function Card({
  title,
  subtitle,
  actions,
  footer,
  tone = "default",
  as: Tag = "section",
  headingLevel = 2,
  className,
  children,
}: CardProps) {
  const titleId = useId();
  const Heading = `h${headingLevel}` as "h1" | "h2" | "h3";
  const classes = ["card", tone === "muted" ? "card-muted" : "", className ?? ""].filter(Boolean).join(" ");
  return (
    <Tag className={classes} aria-labelledby={title ? titleId : undefined}>
      {title || actions ? (
        <div className="card-header">
          <div>
            {title ? (
              <Heading id={titleId} className="card-title">
                {title}
              </Heading>
            ) : null}
            {subtitle ? <p className="card-subtitle">{subtitle}</p> : null}
          </div>
          {actions ? <div className="cluster">{actions}</div> : null}
        </div>
      ) : null}
      {children}
      {footer ? <div className="card-footer">{footer}</div> : null}
    </Tag>
  );
}
