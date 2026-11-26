import { useLayoutEffect, useRef, type ChangeEvent, type ReactNode } from "react";
import { AMOUNT_MAX_DIGITS, groupDigits, toDigits } from "../lib/format";
import Field from "./Field";

export interface AmountFieldProps {
  label: string;
  // digits only ("30000"); shown grouped ("30.000")
  value: string;
  onChange: (digits: string) => void;
  hint?: ReactNode;
  error?: string | null;
  name?: string;
  required?: boolean;
  disabled?: boolean;
  placeholder?: string;
  maxDigits?: number;
  suffix?: string;
}

// Whole-lira amount input: keeps digits only (so "30.000" or "30,000" both mean 30000), at most 15 digits (the
// Finance Profile column limit), shown with tr-TR grouping. The caret stays after the same digit while typing.
export default function AmountField({
  value,
  onChange,
  maxDigits = AMOUNT_MAX_DIGITS,
  suffix = "TL",
  placeholder = "0",
  ...rest
}: AmountFieldProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  // digits to the left of the caret after the last change; applied once the grouped value is rendered
  const pendingCaret = useRef<number | null>(null);

  useLayoutEffect(() => {
    const input = inputRef.current;
    const digitsBefore = pendingCaret.current;
    if (!input || digitsBefore === null || document.activeElement !== input) return;
    pendingCaret.current = null;
    let position = 0;
    let seen = 0;
    while (position < input.value.length && seen < digitsBefore) {
      if (/\d/.test(input.value[position])) seen += 1;
      position += 1;
    }
    input.setSelectionRange(position, position);
  });

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    const raw = event.target.value;
    const caret = event.target.selectionStart ?? raw.length;
    const digits = toDigits(raw, maxDigits);
    pendingCaret.current = Math.min(toDigits(raw.slice(0, caret), maxDigits).length, digits.length);
    onChange(digits);
  };

  return (
    <Field
      {...rest}
      ref={inputRef}
      type="text"
      inputMode="numeric"
      autoComplete="off"
      className="input-numeric"
      value={groupDigits(value)}
      onChange={handleChange}
      placeholder={placeholder}
      suffix={suffix}
    />
  );
}
