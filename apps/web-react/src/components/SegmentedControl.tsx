import { useId, type ReactNode } from "react";

export interface SegmentedOption<T extends string | number> {
  value: T;
  label: string;
  // accessible description of the option (e.g. the impatience hint); shown below when selected
  description?: string;
}

export interface SegmentedControlProps<T extends string | number> {
  legend: string;
  options: SegmentedOption<T>[];
  value: T;
  onChange: (value: T) => void;
  // extra line under the options; defaults to the selected option's description
  hint?: ReactNode;
  disabled?: boolean;
  name?: string;
}

// a radio group that looks like a segmented control: arrow keys work, getByRole("radio") finds the options
export default function SegmentedControl<T extends string | number>({
  legend,
  options,
  value,
  onChange,
  hint,
  disabled = false,
  name,
}: SegmentedControlProps<T>) {
  const autoName = useId();
  const groupName = name ?? autoName;
  const hintId = `${groupName}-hint`;
  const selected = options.find((option) => option.value === value);
  const hintText = hint ?? selected?.description;

  return (
    <fieldset className="segmented" disabled={disabled} aria-describedby={hintText ? hintId : undefined}>
      <legend className="field-label">{legend}</legend>
      <div className="segmented-options">
        {options.map((option) => (
          <label key={String(option.value)} className="segmented-option" title={option.description}>
            <input
              type="radio"
              name={groupName}
              value={String(option.value)}
              checked={option.value === value}
              onChange={() => onChange(option.value)}
              aria-label={option.description ? `${option.label}: ${option.description}` : option.label}
            />
            <span aria-hidden="true">{option.label}</span>
          </label>
        ))}
      </div>
      {hintText ? (
        <p id={hintId} className="field-hint" aria-live="polite">
          {hintText}
        </p>
      ) : null}
    </fieldset>
  );
}
