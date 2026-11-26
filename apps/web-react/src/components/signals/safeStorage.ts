// Browser storage that never throws. localStorage / sessionStorage can be missing (server render, tests), blocked
// (privacy mode, sandboxed frame) or full; every caller then simply keeps its state in memory for this page view.
// Used by the assistant transcript, the portfolio preferences and the 4.4 watchlist. (A candidate for src/lib/ if
// other pages need it.)

export type StorageKind = "local" | "session";

export function browserStorage(kind: StorageKind): Storage | null {
  try {
    const store = kind === "local" ? globalThis.localStorage : globalThis.sessionStorage;
    return store ?? null;
  } catch {
    return null;
  }
}

// parsed JSON, or null when there is nothing (or nothing readable) under the key
export function readJson(storage: Storage | null, key: string): unknown {
  if (!storage) return null;
  try {
    const raw = storage.getItem(key);
    return raw ? (JSON.parse(raw) as unknown) : null;
  } catch {
    return null;
  }
}

// true when the value was stored
export function writeJson(storage: Storage | null, key: string, value: unknown): boolean {
  if (!storage) return false;
  try {
    storage.setItem(key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export function removeKey(storage: Storage | null, key: string): boolean {
  if (!storage) return false;
  try {
    storage.removeItem(key);
    return true;
  } catch {
    return false;
  }
}

// storage keys are per signed-in user, so two people sharing a browser never see each other's lists
export function userKey(base: string, userId: string | null | undefined): string {
  return `${base}.${userId && userId.length > 0 ? userId : "anonymous"}`;
}
