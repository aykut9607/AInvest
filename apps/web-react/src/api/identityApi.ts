import { GATEWAY_URL } from "../config";
import type { AuthSession } from "../types/api";
import { ApiError, SessionExpiredError, errorFrom, request, throwIfRateLimited } from "./http";
import { sessionFromTokens } from "./session";

interface AuthResponse {
  accessToken: string;
  refreshToken: string;
}

// The /auth routes need no token at the gateway. POST /auth/login is limited to 5 attempts a minute per IP
// (429 + Retry-After). Identity: 400 validation, 401 wrong credentials, 409 e-mail already registered.

export function login(email: string, password: string): Promise<AuthSession> {
  return authenticate("/auth/login", { email, password }, "Giriş yapılamadı.", email);
}

export function register(email: string, password: string): Promise<AuthSession> {
  return authenticate("/auth/register", { email, password }, "Kayıt oluşturulamadı.", email);
}

// trades the refresh token for a new pair; Identity rotates it, so the old refresh token stops working
export async function refresh(refreshToken: string, email = ""): Promise<AuthSession> {
  try {
    return await authenticate("/auth/refresh", { refreshToken }, "Oturum yenilenemedi.", email);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) throw new SessionExpiredError();
    throw err;
  }
}

async function authenticate(path: string, payload: object, fallback: string, email: string): Promise<AuthSession> {
  const response = await request<AuthResponse>(`${GATEWAY_URL}${path}`, { method: "POST", body: payload });
  throwIfRateLimited(response, (seconds) => `Çok fazla deneme. ${seconds} saniye sonra tekrar deneyin.`);

  const { status, body } = response;
  if ((status !== 200 && status !== 201) || !body?.accessToken || !body.refreshToken) {
    throw errorFrom(response, fallback);
  }
  try {
    return sessionFromTokens(body.accessToken, body.refreshToken, email);
  } catch {
    throw new ApiError("Kimlik servisinden gelen oturum bilgisi okunamadı.", status);
  }
}
