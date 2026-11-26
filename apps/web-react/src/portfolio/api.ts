// Talks to the Edge Gateway only. The pages need nothing but a PortfolioApi, so another app (with its own login and token
// handling) can use them by passing its own implementation.

export const GATEWAY_URL: string = import.meta.env.VITE_GATEWAY_URL ?? "http://localhost:5000";

export interface Session {
  accessToken: string;
  refreshToken: string;
  // JWT "sub" claim: the userId in every service
  userId: string;
  email: string;
}

export interface PortfolioApi {
  userId: string;
  email: string;
  // unwraps the { data, success, message } envelope; throws ApiError otherwise
  get<T>(path: string): Promise<T>;
  send<T>(method: "PUT" | "POST", path: string, body?: unknown): Promise<T>;
  // an answer without the envelope (the AI service)
  raw<T>(path: string, timeoutMs?: number, body?: unknown): Promise<T>;
}

export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.status = status;
  }
}

interface Answer {
  status: number;
  body: unknown;
  retryAfter: number | null;
}

async function call(path: string, method: string, token: string | null, body: unknown, timeoutMs: number): Promise<Answer> {
  const stop = new AbortController();
  const timer = setTimeout(() => stop.abort(), timeoutMs);
  try {
    const response = await fetch(GATEWAY_URL + path, {
      method,
      headers: { "Content-Type": "application/json", ...(token ? { Authorization: `Bearer ${token}` } : {}) },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: stop.signal,
    });
    const text = await response.text();
    let parsed: unknown = null;
    try {
      parsed = text ? JSON.parse(text) : null;
    } catch {
      parsed = null;
    }
    const retryAfter = Number(response.headers.get("Retry-After"));
    return { status: response.status, body: parsed, retryAfter: Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null };
  } catch {
    throw new ApiError("Ağ geçidine ulaşılamıyor. Servisler açık mı?", 0);
  } finally {
    clearTimeout(timer);
  }
}

function messageOf(body: unknown): string {
  const message = body && typeof body === "object" ? (body as { message?: unknown }).message : null;
  return typeof message === "string" ? message : "";
}

// reads the claims without checking the signature: the gateway checks it on every call
function claimsOf(token: string): Record<string, unknown> {
  const part = (token.split(".")[1] ?? "").replace(/-/g, "+").replace(/_/g, "/");
  return JSON.parse(atob(part + "=".repeat((4 - (part.length % 4)) % 4))) as Record<string, unknown>;
}

export async function authenticate(path: "/auth/login" | "/auth/register" | "/auth/refresh", payload: object): Promise<Session> {
  const { status, body, retryAfter } = await call(path, "POST", null, payload, 15000);
  if (status === 429) throw new ApiError(`Çok fazla deneme yapıldı. ${retryAfter ?? 60} saniye sonra yeniden dene.`, status);
  const tokens = body as { accessToken?: string; refreshToken?: string } | null;
  if (status !== 200 || !tokens?.accessToken || !tokens.refreshToken) {
    const known: Record<number, string> = { 401: "E-posta ya da şifre hatalı.", 409: "Bu e-postayla kayıtlı bir hesap var.", 400: "E-posta ya da şifre geçerli değil (şifre en az 8 karakter)." };
    throw new ApiError(known[status] ?? (messageOf(body) || "Giriş yapılamadı."), status);
  }
  const claims = claimsOf(tokens.accessToken);
  return { accessToken: tokens.accessToken, refreshToken: tokens.refreshToken, userId: String(claims.sub), email: String(claims.email ?? "") };
}

// one refresh at a time: Identity rotates the refresh token, a second parallel refresh with the same one would fail
export function createApi(first: Session, onChange: (session: Session | null) => void): PortfolioApi {
  let session = first;
  let refreshing: Promise<boolean> | null = null;

  const refresh = (): Promise<boolean> => {
    refreshing ??= authenticate("/auth/refresh", { refreshToken: session.refreshToken })
      .then((next) => {
        session = { ...next, email: next.email || session.email };
        onChange(session);
        return true;
      })
      .catch(() => false)
      .finally(() => {
        refreshing = null;
      });
    return refreshing;
  };

  const authorized = async (path: string, method: string, body: unknown, timeoutMs: number): Promise<Answer> => {
    const answer = await call(path, method, session.accessToken, body, timeoutMs);
    if (answer.status !== 401) return answer;
    if (await refresh()) {
      const again = await call(path, method, session.accessToken, body, timeoutMs);
      if (again.status !== 401) return again;
    }
    onChange(null);
    throw new ApiError("Oturumun süresi doldu. Yeniden giriş yap.", 401);
  };

  const unwrap = <T>({ status, body, retryAfter }: Answer): T => {
    if (status === 429) throw new ApiError(`Çok sık istek gönderildi. ${retryAfter ?? 60} saniye sonra yeniden dene.`, status);
    const envelope = body as { data?: T; success?: boolean } | null;
    if (status < 200 || status > 299 || !envelope?.success) throw new ApiError(messageOf(body), status);
    return envelope.data as T;
  };

  return {
    userId: session.userId,
    email: session.email,
    get: async <T>(path: string) => unwrap<T>(await authorized(path, "GET", undefined, 20000)),
    send: async <T>(method: "PUT" | "POST", path: string, body?: unknown) => unwrap<T>(await authorized(path, method, body, 20000)),
    raw: async <T>(path: string, timeoutMs = 20000, payload?: unknown) => {
      const { status, body, retryAfter } = await authorized(path, payload === undefined ? "GET" : "POST", payload, timeoutMs);
      if (status === 429) throw new ApiError(`Çok sık istek gönderildi. ${retryAfter ?? 60} saniye sonra yeniden dene.`, status);
      if (status !== 200 || !body) throw new ApiError(messageOf(body), status);
      return body as T;
    },
  };
}
