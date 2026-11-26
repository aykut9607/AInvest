import { useId, type InputHTMLAttributes, type ReactNode, type Ref } from "react";

export interface FieldProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "size"> {
  label: string;
  hint?: ReactNode;
  // shown under the input in red; also sets aria-invalid
  error?: string | null;
  // short unit inside the input on the right, e.g. "TL"
  suffix?: string;
  ref?: Ref<HTMLInputElement>;
}

// label + input + hint/error, wired with ids so getByLabel and screen readers find everything
export default function Field({ label, hint, error, suffix, id, className, ref, ...inputProps }: FieldProps) {
  const autoId = useId();
  const inputId = id ?? autoId;
  const hintId = hint ? `${inputId}-hint` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const inputClasses = ["input", suffix ? "input-has-suffix" : "", className ?? ""].filter(Boolean).join(" ");

  return (
    <div className="field">
      <label className="field-label" htmlFor={inputId}>
        {label}
      </label>
      <div className="input-wrap">
        <input
          ref={ref}
          id={inputId}
          className={inputClasses}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy}
          {...inputProps}
        />
        {suffix ? (
          <span className="input-suffix" aria-hidden="true">
            {suffix}
          </span>
        ) : null}
      </div>
      {hint ? (
        <p id={hintId} className="field-hint">
          {hint}
        </p>
      ) : null}
      {error ? (
        <p id={errorId} className="field-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
