import { afterEach, describe, expect, it, vi } from "vitest";
import { empty, json, makeJwt, mockFetch } from "../test/helpers";
import { ApiError, RateLimitError, SessionExpiredError } from "./http";
import { login, refresh, register } from "./identityApi";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("identityApi", () => {
  it("returns the session with userId = sub", async () => {
    const token = makeJwt({ sub: "u-42", email: "demo.medium@ainvest.local", role: "USER" });
    const { calls } = mockFetch(() => json(200, { accessToken: token, refreshToken: "r1" }));

    const session = await login("demo.medium@ainvest.local", "Demo12345!");

    expect(calls[0].url).toMatch(/\/auth\/login$/);
    expect(calls[0].body).toEqual({ email: "demo.medium@ainvest.local", password: "Demo12345!" });
    expect(session).toEqual({ accessToken: token, refreshToken: "r1", userId: "u-42", email: "demo.medium@ainvest.local" });
  });

  it("explains a login 429 in Turkish with the wait", async () => {
    mockFetch(() => empty(429, { "Retry-After": "30" }));

    const error = await login("a@b.c", "wrong").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(RateLimitError);
    expect((error as RateLimitError).retryAfterSeconds).toBe(30);
    expect((error as RateLimitError).message).toBe("Çok fazla deneme. 30 saniye sonra tekrar deneyin.");
  });

  it("translates Identity's messages", async () => {
    mockFetch(() => json(401, { message: "Invalid email or password" }));
    await expect(login("a@b.c", "wrong")).rejects.toThrow("E-posta adresi veya şifre hatalı.");

    mockFetch(() => json(409, { message: "Email already registered: a@b.c" }));
    const conflict = await register("a@b.c", "12345678").catch((e: unknown) => e);
    expect((conflict as ApiError).status).toBe(409);
    expect((conflict as ApiError).message).toBe("Bu e-posta adresiyle kayıtlı bir hesap zaten var.");

    mockFetch(() => json(400, { message: "Email must be a valid email address; Password must be between 8 and 72 characters" }));
    await expect(register("x", "1")).rejects.toThrow("Geçerli bir e-posta adresi girin. Şifre 8 ile 72 karakter arasında olmalı.");
  });

  it("turns a refused refresh into SessionExpiredError", async () => {
    mockFetch(() => json(401, { message: "Invalid or expired refresh token" }));
    await expect(refresh("old")).rejects.toBeInstanceOf(SessionExpiredError);
  });
});
