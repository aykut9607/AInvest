import { afterEach, describe, expect, it, vi } from "vitest";
import { empty, json, mockFetch } from "../test/helpers";
import { ApiError, isAbortError, messageFrom, request, timeoutFor } from "./http";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const hangUntilAborted = (_call: unknown, init: RequestInit) =>
  new Promise<Response>((_resolve, reject) => {
    init.signal?.addEventListener("abort", () => reject(new DOMException("aborted", "AbortError")));
  });

describe("request", () => {
  it("returns status and parsed body without throwing on HTTP errors", async () => {
    mockFetch(() => json(404, { data: null, success: false, message: "Financial profile not found." }));

    const response = await request("http://localhost:5000/api/Profiles/x");

    expect(response.status).toBe(404);
    expect(response.body).toEqual({ data: null, success: false, message: "Financial profile not found." });
    expect(response.retryAfterSeconds).toBeNull();
  });

  it("sends JSON with a Content-Type only when there is a body", async () => {
    const { calls } = mockFetch(() => json(200, {}));

    await request("http://localhost:5000/auth/login", { method: "POST", body: { email: "a@b", password: "x" } });
    await request("http://localhost:5000/api/financial-iq/x/latest");

    expect(calls[0].headers["Content-Type"]).toBe("application/json");
    expect(calls[0].body).toEqual({ email: "a@b", password: "x" });
    expect(calls[1].headers["Content-Type"]).toBeUndefined();
  });

  it.each([502, 503, 504])("throws ApiError for an empty-body %i from the gateway", async (status) => {
    mockFetch(() => empty(status));

    const error = await request("http://localhost:5000/ai/insights/warnings?x=1").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(status);
    expect((error as ApiError).message).toBe(
      `/ai/insights/warnings arkasındaki servis yanıt vermiyor (${status}). Servis çalışıyor mu?`
    );
  });

  it("passes a service's own 502 with a body on to the caller", async () => {
    mockFetch(() => json(502, { message: "Financial IQ service is unavailable. Please try again later." }));
    const response = await request("http://localhost:5000/api/Profiles/x/calculate-iq", { method: "POST" });
    expect(response.status).toBe(502);
  });

  it("reads Retry-After", async () => {
    mockFetch(() => empty(429, { "Retry-After": "17" }));
    const response = await request("http://localhost:5000/auth/login", { method: "POST", body: {} });
    expect(response.retryAfterSeconds).toBe(17);
  });

  it("turns a network failure into a Turkish ApiError without status", async () => {
    mockFetch(() => {
      throw new TypeError("Failed to fetch");
    });

    const error = await request("http://localhost:5000/api/Profiles/x").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBeUndefined();
    expect((error as ApiError).message).toContain("http://localhost:5000 adresine ulaşılamadı");
  });

  it("times out", async () => {
    vi.useFakeTimers();
    mockFetch(hangUntilAborted);

    const pending = request("http://localhost:5000/api/Profiles/x", { timeoutMs: 1000 }).catch((e: unknown) => e);
    await vi.advanceTimersByTimeAsync(1001);
    const error = await pending;

    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).message).toContain("zaman aşımına uğradı (1 sn)");
  });

  it("passes the caller's abort on as an AbortError", async () => {
    mockFetch(hangUntilAborted);
    const controller = new AbortController();

    const pending = request("http://localhost:5000/api/Profiles/x", { signal: controller.signal }).catch((e: unknown) => e);
    controller.abort();
    const error = await pending;

    expect(isAbortError(error)).toBe(true);
    expect(error).not.toBeInstanceOf(ApiError);
  });
});

describe("timeoutFor", () => {
  it("gives /ai calls 70 s (the model may take 60 s) and everything else 10 s", () => {
    expect(timeoutFor("http://localhost:5000/ai/explain-financial-iq")).toBe(70_000);
    expect(timeoutFor("/ai/assistant/ask")).toBe(70_000);
    expect(timeoutFor("http://localhost:5000/api/Profiles/x")).toBe(10_000);
    expect(timeoutFor("http://localhost:5000/auth/login")).toBe(10_000);
  });
});

describe("messageFrom", () => {
  it("reads { message }", () => {
    expect(messageFrom({ message: "Invalid email or password" }, "x")).toBe("Invalid email or password");
  });

  it("reads FastAPI 422 { detail: [...] } and { detail: string }", () => {
    const body = {
      detail: [
        { loc: ["body", "score"], msg: "Input should be less than or equal to 100" },
        { loc: ["body"], msg: "Value error, factor points add up to 61, not to the score 62" },
      ],
    };
    expect(messageFrom(body, "x")).toBe(
      "score: Input should be less than or equal to 100; Value error, factor points add up to 61, not to the score 62"
    );
    expect(messageFrom({ detail: "Not Found" }, "x")).toBe("Not Found");
  });

  it("reads ASP.NET ValidationProblemDetails", () => {
    const body = {
      title: "One or more validation errors occurred.",
      status: 400,
      errors: { "$.monthlyIncome": ["The JSON value could not be converted to System.Decimal."] },
    };
    expect(messageFrom(body, "x")).toBe("$.monthlyIncome: The JSON value could not be converted to System.Decimal.");
    expect(messageFrom({ title: "Bad Request", errors: {} }, "x")).toBe("Bad Request");
  });

  it("falls back for anything else", () => {
    expect(messageFrom(null, "Yedek")).toBe("Yedek");
    expect(messageFrom({ message: "" }, "Yedek")).toBe("Yedek");
    expect(messageFrom("text", "Yedek")).toBe("Yedek");
  });
});
