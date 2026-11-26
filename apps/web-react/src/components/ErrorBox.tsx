import type { ReactNode } from "react";
import { RateLimitError } from "../api/http";
import { errorMessage } from "../lib/errors";
import Button from "./Button";
import RateLimitNotice from "./RateLimitNotice";

export interface ErrorBoxProps {
  // anything a call threw (ApiError, RateLimitError, SessionExpiredError, string); null/undefined renders nothing
  error: unknown;
  title?: string;
  // shows a "Tekrar dene" button
  onRetry?: () => void;
  retryLabel?: string;
  // wording for a 429 countdown (see RateLimitNotice)
  rateLimitMessage?: (secondsLeft: number) => string;
  onRateLimitDone?: () => void;
  children?: ReactNode;
}

// error message box; a RateLimitError becomes a countdown instead
export default function ErrorBox({
  error,
  title,
  onRetry,
  retryLabel = "Tekrar dene",
  rateLimitMessage,
  onRateLimitDone,
  children,
}: ErrorBoxProps) {
  if (error === null || error === undefined || error === "") return null;

  if (error instanceof RateLimitError) {
    return (
      <RateLimitNotice
        key={error.retryAt}
        seconds={error.retryAfterSeconds}
        message={rateLimitMessage}
        onDone={onRateLimitDone}
      />
    );
  }

  return (
    <div className="notice notice-error" role="alert">
      <svg className="notice-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" aria-hidden="true">
        <circle cx="12" cy="12" r="9" />
        <path d="M12 7v6M12 16.5v.5" strokeLinecap="round" />
      </svg>
      <div className="notice-body">
        {title ? <p className="notice-title">{title}</p> : null}
        <p>{errorMessage(error)}</p>
        {children}
        {onRetry ? (
          <div>
            <Button size="sm" onClick={onRetry}>
              {retryLabel}
            </Button>
          </div>
        ) : null}
      </div>
    </div>
  );
}
