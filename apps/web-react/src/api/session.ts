import type { AuthSession } from "../types/api";

// The signed-in user's tokens, kept outside React: the API layer needs them on every call and swaps them in place
// when the access token is refreshed. Persisted in sessionStorage, so a reload keeps the user signed in and
// closing the tab signs them out (the refresh token lives 7 days at Identity, the tab usually much less).

const STORAGE_KEY = "ainvest.session";

let current: AuthSession | null = null;
const changeListeners = new Set<() => void>();
const expiredListeners = new Set<() => void>();

// sessionStorage can be missing (tests, some embedded browsers) or throw (blocked storage): never let that break
// signing in, the session then simply does not survive a reload
function storage(): Storage | null {
  try {
    return typeof sessionStorage === "undefined" ? null : sessionStorage;
  } catch {
    return null;
  }
}

function persist(session: AuthSession | null): void {
  try {
    const store = storage();
    if (!store) return;
    if (session) store.setItem(STORAGE_KEY, JSON.stringify(session));
    else store.removeItem(STORAGE_KEY);
  } catch {
    // quota or privacy mode: keep the in-memory session only
  }
}

function isSession(value: unknown): value is AuthSession {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.accessToken === "string" &&
    v.accessToken.length > 0 &&
    typeof v.refreshToken === "string" &&
    v.refreshToken.length > 0 &&
    typeof v.userId === "string" &&
    v.userId.length > 0 &&
    typeof v.email === "string"
  );
}

// reads the stored session (called once at start-up; tests call it again after preparing the storage)
export function restoreSession(): AuthSession | null {
  let restored: AuthSession | null;
  try {
    const raw = storage()?.getItem(STORAGE_KEY);
    const parsed: unknown = raw ? JSON.parse(raw) : null;
    restored = isSession(parsed) ? parsed : null;
  } catch {
    restored = null;
  }
  current = restored;
  return current;
}

export function getSession(): AuthSession | null {
  return current;
}

export function setSession(session: AuthSession | null): void {
  current = session;
  persist(session);
  changeListeners.forEach((listener) => listener());
}

export function clearSession(): void {
  setSession(null);
}

// for useSyncExternalStore: called after every change (sign-in, token refresh, sign-out, expiry)
export function subscribeSession(listener: () => void): () => void {
  changeListeners.add(listener);
  return () => changeListeners.delete(listener);
}

// AuthProvider registers here to send the user to /giris with a notice when the refresh token is refused
export function onSessionExpired(listener: () => void): () => void {
  expiredListeners.add(listener);
  return () => expiredListeners.delete(listener);
}

export function expireSession(): void {
  if (current === null) return;
  setSession(null);
  expiredListeners.forEach((listener) => listener());
}

// Reads the claims without verifying the signature: the gateway verifies it on every call. JWT uses base64url
// and the payload is UTF-8 JSON.
export function decodeJwtPayload(token: string): Record<string, unknown> {
  const payload = token.split(".")[1];
  if (!payload) throw new Error("Not a JWT");
  const base64 = payload.replace(/-/g, "+").replace(/_/g, "/");
  const padded = base64 + "=".repeat((4 - (base64.length % 4)) % 4);
  const bytes = Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
  const claims: unknown = JSON.parse(new TextDecoder().decode(bytes));
  if (!claims || typeof claims !== "object") throw new Error("JWT payload is not an object");
  return claims as Record<string, unknown>;
}

// builds the session from Identity's token pair; userId = "sub", the id every other service uses
export function sessionFromTokens(accessToken: string, refreshToken: string, fallbackEmail = ""): AuthSession {
  const claims = decodeJwtPayload(accessToken);
  if (typeof claims.sub !== "string" || claims.sub.length === 0) throw new Error("JWT has no sub claim");
  return {
    accessToken,
    refreshToken,
    userId: claims.sub,
    email: typeof claims.email === "string" && claims.email.length > 0 ? claims.email : fallbackEmail,
  };
}

restoreSession();
