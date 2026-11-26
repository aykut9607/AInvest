import { AI_REQUEST_TIMEOUT_MS, REQUEST_TIMEOUT_MS } from "../config";
import { translateServerMessage } from "../lib/messages";

// Errors the API layer throws. HTTP errors with a body are NOT thrown by request(): the caller sees the status and
// the body and decides (404 is often "nothing yet", not an error).
export class ApiError extends Error {
  readonly status: number | undefined;

  constructor(message: string, status?: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

// 429 from the gateway: POST /auth/login (5 a minute per IP) or /ai/* (10 a minute per user). Empty body,
// the wait is in Retry-After (CORS exposes the header).
export class RateLimitError extends ApiError {
  readonly retryAfterSeconds: number;
  // epoch ms when a new attempt makes sense (also a handy React key: a new error restarts a countdown)
  readonly retryAt: number;

  constructor(retryAfterSeconds: number, message = `Çok fazla istek gönderildi. ${retryAfterSeconds} saniye sonra tekrar deneyin.`) {
    super(message, 429);
    this.name = "RateLimitError";
    this.retryAfterSeconds = retryAfterSeconds;
    this.retryAt = Date.now() + retryAfterSeconds * 1000;
  }
}

// the refresh token was refused (or there is no session): the user has to sign in again
export class SessionExpiredError extends ApiError {
  constructor(message = "Oturumunuzun süresi doldu. Lütfen yeniden giriş yapın.") {
    super(message, 401);
    this.name = "SessionExpiredError";
  }
}

export interface RequestOptions {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  // default: 70 s for /ai/* paths, 10 s otherwise (see timeoutFor)
  timeoutMs?: number;
  // lets a page cancel a call when it unmounts; the caller then gets the AbortError (see isAbortError)
  signal?: AbortSignal;
}

// what the typed API functions (financeApi, iqApi, aiApi, ...) accept: a signal to cancel on unmount
export type CallOptions = Pick<RequestOptions, "signal">;

export interface ApiResponse<T> {
  status: number;
  body: T | null;
  // seconds from the Retry-After header (the gateway sends it with 429), null when absent
  retryAfterSeconds: number | null;
}

// used when a 429 comes without a usable Retry-After: the gateway's windows are one minute long
const DEFAULT_RETRY_AFTER_SECONDS = 60;

export function timeoutFor(url: string): number {
  return /^(https?:\/\/[^/]+)?\/ai\//.test(url) ? AI_REQUEST_TIMEOUT_MS : REQUEST_TIMEOUT_MS;
}

export function isAbortError(err: unknown): boolean {
  return err instanceof DOMException ? err.name === "AbortError" : err instanceof Error && err.name === "AbortError";
}

// small fetch wrapper: JSON in/out, timeout, readable (Turkish) errors when nothing answers
export async function request<T>(url: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
  const timeoutMs = options.timeoutMs ?? timeoutFor(url);
  const controller = new AbortController();
  let timedOut = false;
  const timer = setTimeout(() => {
    timedOut = true;
    controller.abort();
  }, timeoutMs);
  const onCallerAbort = () => controller.abort();
  options.signal?.addEventListener("abort", onCallerAbort);

  let response: Response;
  try {
    if (options.signal?.aborted) controller.abort();
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers: {
        Accept: "application/json",
        ...(options.body === undefined ? {} : { "Content-Type": "application/json" }),
        ...options.headers,
      },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
  } catch (err) {
    // the caller cancelled: pass the AbortError on so it can be ignored
    if (options.signal?.aborted && !timedOut) throw err;
    const origin = url.match(/^https?:\/\/[^/]+/)?.[0] ?? url;
    if (timedOut) {
      throw new ApiError(`İstek zaman aşımına uğradı (${Math.round(timeoutMs / 1000)} sn). ${origin} yanıt vermedi.`);
    }
    // network error: most likely the gateway is not running
    throw new ApiError(`${origin} adresine ulaşılamadı. Ağ geçidi (gateway) çalışıyor mu?`);
  } finally {
    clearTimeout(timer);
    options.signal?.removeEventListener("abort", onCallerAbort);
  }

  const text = await response.text();
  let body: unknown = null;
  if (text) {
    try {
      body = JSON.parse(text);
    } catch {
      body = null;
    }
  }

  // an empty 502/503/504 comes from the gateway itself: the service behind it is down or not answering
  // (a service's own 502, e.g. Finance when IQ fails, has a body with a message and is passed on as usual)
  if (body === null && [502, 503, 504].includes(response.status)) {
    const path = url.replace(/^https?:\/\/[^/]+/, "").split("?")[0];
    throw new ApiError(`${path} arkasındaki servis yanıt vermiyor (${response.status}). Servis çalışıyor mu?`, response.status);
  }

  const retryAfter = Number(response.headers.get("Retry-After"));
  return {
    status: response.status,
    body: body as T | null,
    retryAfterSeconds: Number.isFinite(retryAfter) && retryAfter > 0 ? Math.ceil(retryAfter) : null,
  };
}

export function throwIfRateLimited(response: ApiResponse<unknown>, message?: (seconds: number) => string): void {
  if (response.status !== 429) return;
  const seconds = response.retryAfterSeconds ?? DEFAULT_RETRY_AFTER_SECONDS;
  throw new RateLimitError(seconds, message?.(seconds));
}

// Error text from any AInvest service body:
// - { message } (.NET Result envelope, Identity ErrorResponse, AI HTTPException)
// - { detail: [{ loc, msg }] } or { detail: "..." } (FastAPI 422)
// - { title, errors: { Field: ["..."] } } (ASP.NET ValidationProblemDetails when the body cannot be bound)
export function messageFrom(body: unknown, fallback: string): string {
  if (!body || typeof body !== "object") return fallback;
  const record = body as Record<string, unknown>;

  if (typeof record.message === "string" && record.message.length > 0) return record.message;

  if (typeof record.detail === "string" && record.detail.length > 0) return record.detail;
  if (Array.isArray(record.detail)) {
    const parts = record.detail
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const { loc, msg } = item as { loc?: unknown; msg?: unknown };
        if (typeof msg !== "string") return null;
        const field = Array.isArray(loc) && loc.length > 0 ? String(loc[loc.length - 1]) : "";
        return field && field !== "body" ? `${field}: ${msg}` : msg;
      })
      .filter((part): part is string => part !== null);
    if (parts.length > 0) return parts.join("; ");
  }

  if (record.errors && typeof record.errors === "object") {
    const parts = Object.entries(record.errors as Record<string, unknown>).flatMap(([field, messages]) =>
      Array.isArray(messages) ? messages.filter((m): m is string => typeof m === "string").map((m) => (field ? `${field}: ${m}` : m)) : []
    );
    if (parts.length > 0) return parts.join("; ");
  }
  if (typeof record.title === "string" && record.title.length > 0) return record.title;

  return fallback;
}

// ApiError for an unexpected status: the service's own message (translated when known) or the fallback
export function errorFrom(response: ApiResponse<unknown>, fallback: string): ApiError {
  return new ApiError(translateServerMessage(messageFrom(response.body, fallback)), response.status);
}
