import { useId, type FormEvent, type KeyboardEvent, type Ref } from "react";
import { ASSISTANT_QUESTION_MAX_LENGTH } from "../../api/aiApi";
import Button from "../Button";
import { normalizeQuestion } from "./transcript";

export interface ComposerProps {
  value: string;
  onChange: (value: string) => void;
  onSend: (question: string) => void;
  // waiting for an answer, or held back by the rate limit
  disabled: boolean;
  busy: boolean;
  textareaRef?: Ref<HTMLTextAreaElement>;
}

// Question input: Enter sends, Shift+Enter adds a line, at most 500 characters (the AI service's limit).
export default function Composer({ value, onChange, onSend, disabled, busy, textareaRef }: ComposerProps) {
  const id = useId();
  const counterId = `${id}-counter`;
  const hintId = `${id}-hint`;
  const question = normalizeQuestion(value);
  const left = ASSISTANT_QUESTION_MAX_LENGTH - value.length;

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    if (!disabled && question) onSend(question);
  };

  const handleKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    // Enter sends; Shift+Enter is a new line; an IME composition (e.g. Japanese input) keeps Enter for itself
    if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) {
      event.preventDefault();
      submit();
    }
  };

  return (
    <form className="composer" onSubmit={submit} aria-label="Asistana soru sor">
      <label className="field-label" htmlFor={id}>
        Sorun
      </label>
      <textarea
        ref={textareaRef}
        id={id}
        className="textarea composer-input"
        rows={2}
        maxLength={ASSISTANT_QUESTION_MAX_LENGTH}
        value={value}
        onChange={(event) => onChange(event.target.value.slice(0, ASSISTANT_QUESTION_MAX_LENGTH))}
        onKeyDown={handleKeyDown}
        placeholder="Örneğin: Acil durum fonum kaç ay yeter?"
        disabled={disabled}
        aria-describedby={`${hintId} ${counterId}`}
      />
      <div className="composer-bar">
        <p id={hintId} className="field-hint">
          Enter gönderir, Shift+Enter yeni satır.
        </p>
        <span id={counterId} className={`composer-counter${left <= 50 ? " is-near" : ""}`}>
          {value.length}/{ASSISTANT_QUESTION_MAX_LENGTH}
        </span>
        <Button type="submit" variant="primary" disabled={disabled || !question} loading={busy} loadingLabel="Bekleniyor…">
          Gönder
        </Button>
      </div>
    </form>
  );
}
