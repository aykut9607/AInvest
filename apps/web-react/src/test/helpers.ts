// Test helpers: an in-memory Storage, JWTs with chosen claims and a programmable fetch mock.
import { vi } from "vitest";

export class MemoryStorage implements Storage {
  private items = new Map<string, string>();

  get length(): number {
    return this.items.size;
  }
  clear(): void {
    this.items.clear();
  }
  getItem(key: string): string | null {
    return this.items.get(key) ?? null;
  }
  key(index: number): string | null {
    return [...this.items.keys()][index] ?? null;
  }
  removeItem(key: string): void {
    this.items.delete(key);
  }
  setItem(key: string, value: string): void {
    this.items.set(key, String(value));
  }
}

// UTF-8 JSON -> base64url, like a real JWT segment (no Buffer: this file is type-checked with the browser libs)
export function base64url(text: string): string {
  let binary = "";
  new TextEncoder().encode(text).forEach((byte) => {
    binary += String.fromCharCode(byte);
  });
  return btoa(binary).replace(/\+/g, "-").replace(/\//g, "_").replace(/=+$/, "");
}

// unsigned is fine: the client never verifies the signature (the gateway does)
export function makeJwt(claims: Record<string, unknown>): string {
  return `${base64url(JSON.stringify({ alg: "HS512", typ: "JWT" }))}.${base64url(JSON.stringify(claims))}.signature`;
}

export interface MockCall {
  url: string;
  method: string;
  headers: Record<string, string>;
  body: unknown;
}

export type MockHandler = (call: MockCall, init: RequestInit) => Response | Promise<Response>;

// replaces global fetch; every call is recorded with its parsed JSON body and headers
export function mockFetch(handler: MockHandler) {
  const calls: MockCall[] = [];
  const fn = vi.fn(async (input: string | URL | Request, init: RequestInit = {}) => {
    const url = typeof input === "string" ? input : input instanceof URL ? input.href : input.url;
    const headers = { ...(init.headers as Record<string, string> | undefined) };
    const body = typeof init.body === "string" ? JSON.parse(init.body) : undefined;
    const call: MockCall = { url, method: init.method ?? "GET", headers, body };
    calls.push(call);
    return handler(call, init);
  });
  vi.stubGlobal("fetch", fn);
  return { fn, calls };
}

export function json(status: number, body: unknown, headers: Record<string, string> = {}): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json", ...headers } });
}

export function empty(status: number, headers: Record<string, string> = {}): Response {
  return new Response(null, { status, headers });
}

export function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
