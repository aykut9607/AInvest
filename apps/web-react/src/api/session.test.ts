import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { base64url, makeJwt, MemoryStorage } from "../test/helpers";
import {
  clearSession,
  decodeJwtPayload,
  expireSession,
  getSession,
  onSessionExpired,
  restoreSession,
  sessionFromTokens,
  setSession,
  subscribeSession,
} from "./session";

const KEY = "ainvest.session";
const SESSION = { accessToken: "a.b.c", refreshToken: "r", userId: "user-1", email: "demo@ainvest.local" };

beforeEach(() => {
  vi.stubGlobal("sessionStorage", new MemoryStorage());
});

afterEach(() => {
  clearSession();
  vi.unstubAllGlobals();
});

describe("session persistence", () => {
  it("stores the session in sessionStorage and restores it after a reload", () => {
    setSession(SESSION);
    expect(JSON.parse(sessionStorage.getItem(KEY) ?? "null")).toEqual(SESSION);

    // a reload: module state is gone, sessionStorage is not
    setSession(null);
    sessionStorage.setItem(KEY, JSON.stringify(SESSION));
    expect(restoreSession()).toEqual(SESSION);
    expect(getSession()).toEqual(SESSION);
  });

  it("clears the stored session on sign-out", () => {
    setSession(SESSION);
    clearSession();
    expect(getSession()).toBeNull();
    expect(sessionStorage.getItem(KEY)).toBeNull();
  });

  it("ignores a corrupted or incomplete stored session", () => {
    sessionStorage.setItem(KEY, "{not json");
    expect(restoreSession()).toBeNull();
    sessionStorage.setItem(KEY, JSON.stringify({ accessToken: "a", userId: "u" }));
    expect(restoreSession()).toBeNull();
  });

  it("keeps working when storage throws (blocked storage, privacy mode)", () => {
    const broken = new MemoryStorage();
    broken.getItem = () => {
      throw new Error("SecurityError");
    };
    broken.setItem = () => {
      throw new Error("QuotaExceededError");
    };
    vi.stubGlobal("sessionStorage", broken);

    expect(() => setSession(SESSION)).not.toThrow();
    expect(getSession()).toEqual(SESSION);
    expect(restoreSession()).toBeNull();
  });

  it("works without any sessionStorage", () => {
    vi.stubGlobal("sessionStorage", undefined);
    expect(() => setSession(SESSION)).not.toThrow();
    expect(getSession()).toEqual(SESSION);
  });

  it("notifies subscribers on every change and expiry listeners only on expiry", () => {
    const changed = vi.fn();
    const expired = vi.fn();
    const stopChanges = subscribeSession(changed);
    const stopExpiry = onSessionExpired(expired);

    setSession(SESSION);
    clearSession();
    expect(changed).toHaveBeenCalledTimes(2);
    expect(expired).not.toHaveBeenCalled();

    setSession(SESSION);
    expireSession();
    expect(expired).toHaveBeenCalledTimes(1);
    expect(getSession()).toBeNull();

    // nothing left to expire
    expireSession();
    expect(expired).toHaveBeenCalledTimes(1);

    stopChanges();
    stopExpiry();
  });
});

describe("JWT decoding", () => {
  it("reads sub and email from a base64url, UTF-8 payload", () => {
    const token = makeJwt({ sub: "8c1d0f3e-1111-4c22-9a33-abcdefabcdef", email: "şule.öztürk@örnek.com", role: "USER", x: "??>>" });

    expect(decodeJwtPayload(token)).toMatchObject({ sub: "8c1d0f3e-1111-4c22-9a33-abcdefabcdef", email: "şule.öztürk@örnek.com" });
    expect(sessionFromTokens(token, "refresh")).toEqual({
      accessToken: token,
      refreshToken: "refresh",
      userId: "8c1d0f3e-1111-4c22-9a33-abcdefabcdef",
      email: "şule.öztürk@örnek.com",
    });
  });

  it("uses the fallback e-mail when the token has none and rejects a token without sub", () => {
    expect(sessionFromTokens(makeJwt({ sub: "u1" }), "r", "girilen@ainvest.local").email).toBe("girilen@ainvest.local");
    expect(() => sessionFromTokens(makeJwt({ email: "x@y" }), "r")).toThrow();
    expect(() => decodeJwtPayload("not-a-jwt")).toThrow();
    expect(decodeJwtPayload(`x.${base64url('{"sub":"s"}')}.y`)).toEqual({ sub: "s" });
  });
});
