import type { ButtonHTMLAttributes } from "react";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: "md" | "sm";
  block?: boolean;
  // shows a small spinner, disables the button and sets aria-busy
  loading?: boolean;
  loadingLabel?: string;
}

// For a link that looks like a button use the same classes: <Link className="btn btn-primary">
export default function Button({
  variant = "secondary",
  size = "md",
  block = false,
  loading = false,
  loadingLabel,
  type = "button",
  className,
  disabled,
  children,
  ...rest
}: ButtonProps) {
  const classes = ["btn", `btn-${variant}`, size === "sm" ? "btn-sm" : "", block ? "btn-block" : "", className ?? ""]
    .filter(Boolean)
    .join(" ");
  return (
    <button type={type} className={classes} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <span className="spinner-circle" aria-hidden="true" style={{ width: 14, height: 14 }} /> : null}
      {loading && loadingLabel ? loadingLabel : children}
    </button>
  );
}
