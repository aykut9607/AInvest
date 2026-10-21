import { REQUEST_TIMEOUT_MS } from "../config";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

// small fetch wrapper: JSON in/out, timeout, and readable error messages for every service
export async function request<T>(
  url: string,
  options: { method?: string; body?: unknown } = {}
): Promise<{ status: number; body: T | null }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? "GET",
      headers: { "Content-Type": "application/json" },
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

  return { status: response.status, body: body as T | null };
}

// both the .NET Result envelope and the Identity ErrorResponse carry a "message" field
export function messageFrom(body: unknown, fallback: string): string {
  if (body && typeof body === "object" && "message" in body) {
    const message = (body as { message?: unknown }).message;
    if (typeof message === "string" && message.length > 0) return message;
  }
  return fallback;
}
