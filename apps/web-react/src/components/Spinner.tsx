export interface SpinnerProps {
  // read by screen readers and shown next to the circle unless labelHidden
  label?: string;
  labelHidden?: boolean;
  size?: "sm" | "md" | "lg";
  // "block" centres it with vertical padding (page or card loading state)
  layout?: "inline" | "block";
}

export default function Spinner({ label = "Yükleniyor…", labelHidden = false, size = "md", layout = "inline" }: SpinnerProps) {
  const spinner = (
    <span className={`spinner spinner-${size}`} role="status" aria-live="polite">
      <span className="spinner-circle" aria-hidden="true" />
      <span className={labelHidden ? "visually-hidden" : undefined}>{label}</span>
    </span>
  );
  return layout === "block" ? <div className="spinner-block">{spinner}</div> : spinner;
}
