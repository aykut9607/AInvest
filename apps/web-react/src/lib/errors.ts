import { ApiError, RateLimitError } from "../api/http";

// one place that turns anything a call threw into text for the user
export function errorMessage(err: unknown, fallback = "Beklenmeyen bir hata oluştu. Lütfen tekrar deneyin."): string {
  if (err instanceof ApiError) return err.message;
  if (typeof err === "string" && err.length > 0) return err;
  return fallback;
}

export function isRateLimitError(err: unknown): err is RateLimitError {
  return err instanceof RateLimitError;
}
