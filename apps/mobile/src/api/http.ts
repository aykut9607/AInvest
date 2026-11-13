import { REQUEST_TIMEOUT_MS } from "../config";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

// small fetch wrapper: JSON in/out, timeout, and readable error messages for every service
export interface RequestOptions {
  method?: string;
  body?: unknown;
  // e.g. the Authorization header for calls that need a token
  headers?: Record<string, string>;
}

export interface ApiResponse<T> {
  status: number;
  body: T | null;
  // seconds from the Retry-After header (the gateway sends it with 429), null when absent
  retryAfterSeconds: number | null;
}

export async function request<T>(url: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers: { "Content-Type": "application/json", ...options.headers },
      body: options.body === undefined ? undefined : JSON.stringify(options.body),
      signal: controller.signal,
    });
  } catch (err) {
    // network error or timeout - the service is most likely not running
    // regex instead of new URL(): React Native's URL does not implement every property
    const origin = url.match(/^https?:\/\/[^/]+/)?.[0] ?? url;
    const reason = controller.signal.aborted ? "timed out" : err instanceof Error ? err.message : String(err);
    throw new ApiError(`Cannot reach ${origin} (${reason}). Is the service running?`);
  } finally {
    clearTimeout(timer);
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
    const path = url.replace(/^https?:\/\/[^/]+/, "");
    throw new ApiError(`The service behind ${path} is not responding (${response.status}). Is it running?`, response.status);
  }

  const retryAfter = Number(response.headers.get("Retry-After"));
  return {
    status: response.status,
    body: body as T | null,
    retryAfterSeconds: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null,
  };
}

// both the .NET Result envelope and the Identity ErrorResponse carry a "message" field
export function messageFrom(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "message" in body) {
    const message = (body as { message?: unknown }).message;
    if (typeof message === "string" && message.length > 0) return message;
  }
  return fallback;
}
