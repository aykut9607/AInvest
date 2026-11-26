import { expect, type Page } from "@playwright/test";

// Shared steps for the e2e specs. The demo accounts come from `python infra/seed/seed_demo_users.py`.
// The gateway allows 5 logins a minute per IP, so every spec signs in as few times as it can.

export const DEMO_PASSWORD = "Demo12345!";

export async function signIn(page: Page, email: string, password: string = DEMO_PASSWORD) {
  await page.goto("/giris");
  await page.getByLabel("E-posta").fill(email);
  await page.getByLabel("Şifre", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Giriş yap" }).click();
}

// demo users already have a profile, so a sign-in lands on the dashboard
export async function signInToDashboard(page: Page, email: string, password: string = DEMO_PASSWORD) {
  await signIn(page, email, password);
  await expect(page).toHaveURL(/\/panel$/);
}

export async function openFromMenu(page: Page, label: string, path: RegExp) {
  await page.getByRole("navigation", { name: "Ana menü", exact: true }).getByRole("link", { name: label, exact: true }).click();
  await expect(page).toHaveURL(path);
}
