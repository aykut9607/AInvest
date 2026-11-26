import { expect, test } from "@playwright/test";
import { signIn } from "./helpers.ts";

// Needs the running stack (Identity, Finance Profile, Financial IQ, Edge Gateway, `npm run dev`) and the demo accounts
// from `python infra/seed/seed_demo_users.py`. Run: npm run e2e. The gateway allows 5 logins a minute per IP.

const DEMO_EMAIL = "demo.medium@ainvest.local";

test("demo user signs in, the saved profile loads, save & calculate lands on the dashboard", async ({ page }) => {
  await signIn(page, DEMO_EMAIL);

  // the demo user already has a profile, so the sign-in goes to the dashboard
  await expect(page).toHaveURL(/\/panel$/);
  await expect(page.getByRole("button", { name: "Çıkış" })).toBeVisible();

  await page.getByRole("navigation", { name: "Ana menü", exact: true }).getByRole("link", { name: "Profil" }).click();
  await expect(page).toHaveURL(/\/profil$/);

  const income = page.getByLabel("Aylık gelir");
  await expect(income).not.toHaveValue("");
  // one answer in the impatience group (the payment habit groups have their own radios)
  await expect(page.locator('input[name="impatienceLevel"]:checked')).toHaveCount(1);

  await page.getByRole("button", { name: "Kaydet ve hesapla" }).click();
  await expect(page).toHaveURL(/\/panel$/);
});

test("a new account starts with an empty profile form", async ({ page }) => {
  const email = `e2e-${Date.now()}-${Math.random().toString(36).slice(2, 8)}@ainvest.local`;

  await page.goto("/kayit");
  await page.getByLabel("E-posta").fill(email);
  await page.getByLabel("Şifre", { exact: true }).fill("E2eTest12345!");
  await page.getByLabel("Şifre (tekrar)").fill("E2eTest12345!");
  await page.getByRole("button", { name: "Kayıt ol" }).click();

  await expect(page).toHaveURL(/\/profil$/);
  await expect(page.getByText("Henüz kayıtlı profilin yok")).toBeVisible();
  await expect(page.getByLabel("Aylık gelir")).toHaveValue("");
  await expect(page.getByLabel("Toplam borç")).toHaveValue("");

  // the client check runs before anything is sent
  await page.getByRole("button", { name: "Kaydet ve hesapla" }).click();
  await expect(page.getByText("Aylık gelir sıfırdan büyük olmalı.")).toBeVisible();
});

test("protected pages send a signed-out visitor to the sign-in page", async ({ page }) => {
  await page.goto("/asistan");
  await expect(page).toHaveURL(/\/giris$/);
  await expect(page.getByRole("heading", { name: "Giriş yap" })).toBeVisible();
});
