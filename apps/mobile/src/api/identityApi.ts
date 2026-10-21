import { API } from "../config";
import type { AuthSession } from "../types";
import { ApiError, messageFrom, request } from "./http";

interface AuthResponse {
  accessToken: string;
  refreshToken: string;
}

export function login(email: string, password: string): Promise<AuthSession> {
  return authenticate("/auth/login", email, password, "Login failed.");
}

export function register(email: string, password: string): Promise<AuthSession> {
  return authenticate("/auth/register", email, password, "Registration failed.");
}

async function authenticate(
  path: string,
  email: string,
  password: string,
  fallback: string
): Promise<AuthSession> {
  const { status, body } = await request<AuthResponse>(`${API.identity}${path}`, {
    method: "POST",
    body: { email, password },
  });

  if (status !== 200 || !body?.accessToken) {
    throw new ApiError(messageFrom(body, fallback), status);
  }

  const claims = decodeJwtPayload(body.accessToken);
  return {
    accessToken: body.accessToken,
    refreshToken: body.refreshToken,
    userId: String(claims.sub),
    email: String(claims.email ?? email),
  };
}

// reads the claims without verifying the signature - verification belongs to the server (Gateway later)
function decodeJwtPayload(token: string): Record<string, unknown> {
  const payload = token.split(".")[1] ?? "";
  // JWT uses base64url: swap the url-safe characters back and restore the padding
  const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  return JSON.parse(atob(padded));
}
