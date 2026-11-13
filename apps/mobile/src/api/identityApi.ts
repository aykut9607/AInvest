import { GATEWAY_URL } from "../config";
import type { AuthSession } from "../types";
import { ApiError, messageFrom, request } from "./http";

interface AuthResponse {
  accessToken: string;
  refreshToken: string;
}

export function login(email: string, password: string): Promise<AuthSession> {
  return authenticate("/auth/login", { email, password }, "Login failed.");
}

export function register(email: string, password: string): Promise<AuthSession> {
  return authenticate("/auth/register", { email, password }, "Registration failed.");
}

// trades the refresh token for a new pair; Identity rotates it, so the old refresh token stops working
export function refresh(refreshToken: string): Promise<AuthSession> {
  return authenticate("/auth/refresh", { refreshToken }, "Your session has expired. Please sign in again.");
}

// the /auth routes need no token at the gateway; POST /auth/login is limited to 5 attempts per minute per IP
async function authenticate(path: string, payload: object, fallback: string): Promise<AuthSession> {
  const { status, body, retryAfterSeconds } = await request<AuthResponse>(`${GATEWAY_URL}${path}`, {
    method: "POST",
    body: payload,
  });

  if (status === 429) {
    const wait = retryAfterSeconds ? ` Try again in ${retryAfterSeconds} seconds.` : " Try again in a minute.";
    throw new ApiError(`Too many attempts.${wait}`, status);
  }
  if (status !== 200 || !body?.accessToken) {
    throw new ApiError(messageFrom(body, fallback), status);
  }

  const claims = decodeJwtPayload(body.accessToken);
  return {
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
    userId: String(claims.sub),
    email: String(claims.email ?? ""),
  };
}

// reads the claims without verifying the signature - the gateway verifies it on every call
function decodeJwtPayload(token: string): Record<string, unknown> {
  const payload = token.split(".")[1] ?? "";
  // JWT uses base64url: swap the url-safe characters back and restore the padding
  const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  return JSON.parse(atob(padded));
}
