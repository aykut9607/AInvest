import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { deferred, empty, json, makeJwt, MemoryStorage, mockFetch } from "../test/helpers";
import { authorizedRequest, currentUserId } from "./authorizedRequest";
import { askAssistant } from "./aiApi";
import { calculateIq, getProfile } from "./financeApi";
import { ApiError, RateLimitError, SessionExpiredError } from "./http";
import { clearSession, getSession, onSessionExpired, setSession } from "./session";

const USER_ID = "4f9b2a51-6d0e-4c3b-9f3c-1a2b3c4d5e6f";
const OLD_ACCESS = makeJwt({ sub: USER_ID, email: "demo.medium@ainvest.local", n: 1 });
const NEW_ACCESS = makeJwt({ sub: USER_ID, email: "demo.medium@ainvest.local", n: 2 });

const isRefresh = (url: string) => url.endsWith("/auth/refresh");

let unsubscribe: (() => void) | null = null;
let expiredCount = 0;

beforeEach(() => {
  vi.stubGlobal("sessionStorage", new MemoryStorage());
  setSession({ accessToken: OLD_ACCESS, refreshToken: "refresh-1", userId: USER_ID, email: "demo.medium@ainvest.local" });
  expiredCount = 0;
  unsubscribe = onSessionExpired(() => {
    expiredCount += 1;
  });
});

afterEach(() => {
  unsubscribe?.();
  clearSession();
  vi.unstubAllGlobals();
});

describe("authorizedRequest", () => {
  it("sends the bearer token and never an X-User-Id header", async () => {
    const { calls } = mockFetch(() => json(200, { data: { ok: true }, success: true, message: "" }));

    const response = await authorizedRequest<{ data: { ok: boolean } }>(`/api/Profiles/${USER_ID}`);

    expect(response.status).toBe(200);
    expect(calls).toHaveLength(1);
    expect(calls[0].headers.Authorization).toBe(`Bearer ${OLD_ACCESS}`);
    expect(Object.keys(calls[0].headers).map((h) => h.toLowerCase())).not.toContain("x-user-id");
  });

  it("refreshes once and retries the original request exactly once after a 401", async () => {
    const { calls } = mockFetch((call) => {
      if (isRefresh(call.url)) return json(200, { accessToken: NEW_ACCESS, refreshToken: "refresh-2" });
      return call.headers.Authorization === `Bearer ${NEW_ACCESS}` ? json(200, { data: 1, success: true, message: "" }) : empty(401);
    });

    const response = await authorizedRequest("/api/financial-iq/x/latest");

    expect(response.status).toBe(200);
    expect(calls.map((c) => (isRefresh(c.url) ? "refresh" : "api"))).toEqual(["api", "refresh", "api"]);
    expect(calls[1].body).toEqual({ refreshToken: "refresh-1" });
    expect(getSession()?.accessToken).toBe(NEW_ACCESS);
    expect(getSession()?.refreshToken).toBe("refresh-2");
    // the rotated pair is persisted for a reload
    expect(JSON.parse(sessionStorage.getItem("ainvest.session") ?? "{}").refreshToken).toBe("refresh-2");
  });

  it("shares one refresh between concurrent 401s (Identity rotates the refresh token)", async () => {
    const refreshGate = deferred<void>();
    const { calls } = mockFetch(async (call) => {
      if (isRefresh(call.url)) {
        await refreshGate.promise;
        return json(200, { accessToken: NEW_ACCESS, refreshToken: "refresh-2" });
      }
      return call.headers.Authorization === `Bearer ${NEW_ACCESS}` ? json(200, { path: call.url }) : empty(401);
    });

    const pending = Promise.all([
      authorizedRequest("/api/Profiles/a"),
      authorizedRequest("/api/financial-iq/a/latest"),
      authorizedRequest("/ai/insights/warnings"),
    ]);
    // let all three first attempts come back with 401 before the refresh answers
    await new Promise((resolve) => setTimeout(resolve, 10));
    refreshGate.resolve();
    const responses = await pending;

    expect(responses.map((r) => r.status)).toEqual([200, 200, 200]);
    expect(calls.filter((c) => isRefresh(c.url))).toHaveLength(1);
    expect(calls.filter((c) => !isRefresh(c.url))).toHaveLength(6);
    expect(expiredCount).toBe(0);
  });

  it("does not refresh again for a 401 that comes back after another call already refreshed", async () => {
    const slow = deferred<void>();
    const { calls } = mockFetch(async (call) => {
      if (isRefresh(call.url)) return json(200, { accessToken: NEW_ACCESS, refreshToken: "refresh-2" });
      if (call.url.endsWith("/slow") && call.headers.Authorization === `Bearer ${OLD_ACCESS}`) {
        await slow.promise;
        return empty(401);
      }
      return call.headers.Authorization === `Bearer ${NEW_ACCESS}` ? json(200, {}) : empty(401);
    });

    const slowCall = authorizedRequest("/api/slow");
    await authorizedRequest("/api/fast");
    slow.resolve();
    await slowCall;

    expect(calls.filter((c) => isRefresh(c.url))).toHaveLength(1);
  });

  it("ends the session when the retried request is still 401", async () => {
    mockFetch((call) =>
      isRefresh(call.url) ? json(200, { accessToken: NEW_ACCESS, refreshToken: "refresh-2" }) : empty(401)
    );

    await expect(authorizedRequest("/api/Profiles/a")).rejects.toBeInstanceOf(SessionExpiredError);
    expect(expiredCount).toBe(1);
    expect(getSession()).toBeNull();
    expect(sessionStorage.getItem("ainvest.session")).toBeNull();
  });

  it("ends the session when Identity refuses the refresh token", async () => {
    const { calls } = mockFetch((call) =>
      isRefresh(call.url) ? json(401, { message: "Invalid or expired refresh token" }) : empty(401)
    );

    const error = await authorizedRequest("/api/Profiles/a").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(SessionExpiredError);
    expect((error as SessionExpiredError).message).toContain("Oturumunuzun süresi doldu");
    expect(calls).toHaveLength(2);
    expect(expiredCount).toBe(1);
    expect(getSession()).toBeNull();
  });

  it("keeps the session when the refresh fails because the gateway is unreachable", async () => {
    mockFetch((call) => {
      if (isRefresh(call.url)) throw new TypeError("Failed to fetch");
      return empty(401);
    });

    const error = await authorizedRequest("/api/Profiles/a").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).not.toBeInstanceOf(SessionExpiredError);
    expect(expiredCount).toBe(0);
    expect(getSession()?.refreshToken).toBe("refresh-1");
  });

  it("throws RateLimitError with the Retry-After seconds on 429 (/ai is limited per user)", async () => {
    mockFetch(() => empty(429, { "Retry-After": "42" }));

    const error = await askAssistant("Borcum ne kadar?").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(RateLimitError);
    expect((error as RateLimitError).retryAfterSeconds).toBe(42);
    expect((error as RateLimitError).status).toBe(429);
    expect((error as RateLimitError).message).toContain("42 saniye");
  });

  it("falls back to 60 seconds when a 429 has no Retry-After", async () => {
    mockFetch(() => empty(429));
    const error = await authorizedRequest("/ai/explain-iq-trend").catch((e: unknown) => e);
    expect((error as RateLimitError).retryAfterSeconds).toBe(60);
  });

  it("throws SessionExpiredError without a session and never calls fetch", async () => {
    clearSession();
    const { fn } = mockFetch(() => json(200, {}));

    await expect(authorizedRequest("/api/Profiles/a")).rejects.toBeInstanceOf(SessionExpiredError);
    expect(() => currentUserId()).toThrow(SessionExpiredError);
    expect(fn).not.toHaveBeenCalled();
  });
});

describe("typed API modules", () => {
  it("getProfile uses the token's sub in the path and returns null on 404", async () => {
    const { calls } = mockFetch(() => json(404, { data: null, success: false, message: "Financial profile not found." }));

    await expect(getProfile()).resolves.toBeNull();
    expect(calls[0].url).toMatch(new RegExp(`/api/Profiles/${USER_ID}$`));
  });

  it("turns a FastAPI 422 detail list into a readable message", async () => {
    mockFetch(() =>
      json(422, { detail: [{ type: "string_too_long", loc: ["body", "question"], msg: "String should have at most 500 characters" }] })
    );

    const error = await askAssistant("x".repeat(501)).catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(422);
    expect((error as ApiError).message).toBe("question: String should have at most 500 characters");
  });

  it("translates Finance's 502 message when the IQ service is down", async () => {
    mockFetch(() =>
      json(502, { data: null, success: false, message: "Financial IQ service is unavailable. Please try again later." })
    );

    const error = await calculateIq().catch((e: unknown) => e);

    expect((error as ApiError).status).toBe(502);
    expect((error as ApiError).message).toBe("Finansal IQ servisine şu anda ulaşılamıyor. Lütfen biraz sonra tekrar deneyin.");
  });

  it("keeps the factor breakdown exactly as received and parses a v1 string", async () => {
    const breakdown = {
      version: "v2",
      factors: { CashReserveMonths: 15, DebtToIncomeRatio: 15, SavingsRate: 15, ExpenseRatio: 9, Impatience: 8 },
      warnings: [],
      appliedRule: null,
    };
    mockFetch(() => json(200, { data: { score: 62, segment: "MEDIUM", factorBreakdown: breakdown }, success: true, message: "" }));
    await expect(calculateIq()).resolves.toEqual({ score: 62, segment: "MEDIUM", factorBreakdown: breakdown });

    mockFetch(() =>
      json(200, { data: { score: 62, segment: "MEDIUM", factorBreakdown: JSON.stringify(breakdown) }, success: true, message: "" })
    );
    await expect(calculateIq()).resolves.toEqual({ score: 62, segment: "MEDIUM", factorBreakdown: breakdown });
  });
});
