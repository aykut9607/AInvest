import type { AuthSession } from "../types";

// the tokens of the signed-in user, kept outside React state: the API layer needs them on every call
// and swaps them in place when the access token is refreshed (the screens don't have to re-render for that)
let current: AuthSession | null = null;
let expiredListener: (() => void) | null = null;

export function getSession(): AuthSession | null {
  return current;
}

export function setSession(session: AuthSession | null): void {
  current = session;
}

// App registers this to go back to the sign-in screen when the refresh token is no longer accepted
export function onSessionExpired(listener: (() => void) | null): void {
  expiredListener = listener;
}

export function expireSession(): void {
  current = null;
  expiredListener?.();
}
