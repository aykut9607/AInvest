import { expect, test, type Page } from "@playwright/test";
import { signInToDashboard } from "./helpers.ts";

// Dashboard (/panel) against the running stack: Identity, Finance Profile, Financial IQ, AI/RAG, Edge Gateway and
// `npm run dev`, with the demo accounts from `python infra/seed/seed_demo_users.py`. Run: npm run e2e.
// demo.trend has four calculations (v2: 8 -> 37 -> 62 -> 92; v3: 27 -> 51 -> 79 -> 97) and a debt of 30.000 TL
// paid 3.000 TL a month.
// The gateway allows 5 logins a minute per IP, so the whole file signs in once and shares the page.

const EMAIL = "demo.trend@ainvest.local";

test.describe.configure({ mode: "serial" });

let page: Page;

test.beforeAll(async ({ browser }, testInfo) => {
  page = await browser.newPage({ baseURL: testInfo.project.use.baseURL, locale: "tr-TR" });
  await signInToDashboard(page, EMAIL);
});

test.afterAll(async () => {
  await page?.close();
});

const card = (name: string) => page.getByRole("region", { name, exact: true });

test("shows the latest score, its segment and the five factor bars", async () => {
  const score = card("Finansal IQ skorun");
  // demo.trend's last calculation: 92 under scoring v2, 97 under v3
  await expect(score.getByTestId("score-value")).toHaveText(/^(92|97)$/);
  await expect(score.getByText("YÜKSEK", { exact: false })).toBeVisible();
  await expect(score.getByRole("link", { name: "Profili düzenle" })).toBeVisible();

  const factors = card("Skor dökümü");
  await expect(factors.getByRole("meter")).toHaveCount(5);
  await expect(factors.getByText("Nakit rezervi")).toBeVisible();
});

test("loads the warnings (or says there is nothing to warn about)", async () => {
  const warnings = card("Uyarılar");
  await expect(warnings.getByText(/Önemli bir uyarı yok|KRİTİK|UYARI|BİLGİ|temel uyarı listesi/).first()).toBeVisible();
});

test("draws the score history with four points and shows it as a table", async () => {
  const trend = card("Skor geçmişi");
  await expect(trend.getByTestId("trend-point")).toHaveCount(4);

  const toggle = trend.getByRole("button", { name: "Tablo" });
  await toggle.click();
  await expect(toggle).toHaveAttribute("aria-pressed", "true");
  const rows = trend.getByTestId("trend-table").locator("tbody tr");
  await expect(rows).toHaveCount(4);
  await expect(rows.first()).toContainText("–");
  await expect(rows.last()).toContainText(/92|97/);

  await toggle.click();
  await expect(trend.getByTestId("trend-point")).toHaveCount(4);
});

test("the Coach explains the score on demand", async () => {
  // the local model may take up to a minute; a template answer (Ollama off) is fine too
  test.setTimeout(120_000);
  const coach = card("Koç");
  await coach.getByRole("button", { name: "Skorumu açıkla" }).click();
  const answer = coach.getByTestId("ai-answer");
  await expect(answer).toBeVisible({ timeout: 90_000 });
  await expect(answer.locator(".ai-answer-text p").first()).not.toBeEmpty();
});

test("the debt card shows the payoff and follows the interest rate", async () => {
  const debt = card("Borç ödeme planı");
  // 30.000 TL, 3.000 TL a month, 3,5 % a month
  await expect(debt.getByTestId("debt-months")).toContainText("13 ay");

  await debt.getByRole("button", { name: "Tablo" }).click();
  await expect(debt.getByTestId("debt-table").locator("tbody tr")).toHaveCount(13);
  await debt.getByRole("button", { name: "Tablo" }).click();

  // interest-free: exactly 10 installments
  await debt.getByLabel("Aylık faiz oranı").fill("0");
  await debt.getByRole("button", { name: "Yeniden hesapla" }).click();
  await expect(debt.getByTestId("debt-months")).toContainText("10 ay");

  await debt.getByLabel("Aylık faiz oranı").fill("abc");
  await debt.getByRole("button", { name: "Yeniden hesapla" }).click();
  await expect(debt.getByText("0 ile 100 arasında")).toBeVisible();
});
