import { expect, test } from "@playwright/test";
import { openFromMenu, signInToDashboard } from "./helpers.ts";

// Needs the running stack (Identity, Finance Profile, Financial IQ, AI/RAG, Edge Gateway, `npm run dev`) and the demo
// accounts from `python infra/seed/seed_demo_users.py`. Ollama is optional: without it the assistant answers with its
// deterministic template, which is still an answer. Run: npm run e2e.
// One test, one sign-in: the gateway allows 5 logins a minute per IP and auth-profile.spec.ts uses some of them.

// LOW under both scoring versions (v2: 8, v3: 27); demo.medium is MEDIUM under v2 but HIGH (71) under v3
const DEMO_EMAIL = "demo.low@ainvest.local";

test("demo.low: assistant answers, portfolio respects the IQ risk ceiling, 4.4 page loads", async ({ page }) => {
  // the local model may take up to 60 s for one answer
  test.setTimeout(180_000);
  await signInToDashboard(page, DEMO_EMAIL);

  await test.step("assistant: a suggested question gets an answer", async () => {
    await openFromMenu(page, "Asistan", /\/asistan$/);
    await expect(page.getByText("Piyasa fiyatlarını (kripto, hisse, döviz, altın) henüz göremez.")).toBeVisible();

    await page.getByRole("button", { name: "Finansal IQ skorum kaç?" }).click();
    const conversation = page.getByRole("list", { name: "Asistanla konuşma" });
    await expect(conversation.getByText("Finansal IQ skorum kaç?")).toBeVisible();
    await expect(conversation.getByTestId("ai-answer")).toBeVisible({ timeout: 90_000 });
    await expect(page.getByRole("textbox", { name: "Sorun" })).toBeEnabled();
  });

  await test.step("portfolio: MEDIUM and HIGH are locked for a LOW segment, LOW can be chosen, the sample proposal is shown", async () => {
    await openFromMenu(page, "Portföy", /\/portfoy$/);

    await page.getByRole("radio", { name: /Standart dengeli sepet/ }).check();

    const risk = page.getByRole("group", { name: "Risk seviyesi" });
    await expect(risk.getByRole("radio", { name: /^Yüksek/ })).toBeDisabled();
    await expect(risk.getByRole("radio", { name: /^Orta/ })).toBeDisabled();
    await expect(risk.getByText(/en fazla düşük seviyesine izin veriyor/).first()).toBeVisible();
    const low = risk.getByRole("radio", { name: /^Düşük/ });
    await expect(low).toBeEnabled();
    await low.check();
    await expect(low).toBeChecked();
    await expect(page.getByText("Seçimin hazır")).toBeVisible();

    const table = page.getByRole("table", { name: "Varlık dağılımı tablosu" });
    await expect(table.getByRole("row")).toHaveCount(6); // header + 5 assets
    await expect(table.getByRole("row", { name: /Altın/ })).toContainText("%30");
    await expect(table.getByRole("row", { name: /Altın/ })).toContainText("1.740 TL");
  });

  await test.step("4.4: the page shows the engine's data or the empty state", async () => {
    await openFromMenu(page, "Piyasa (4.4)", /\/piyasa$/);
    await expect(page.getByRole("heading", { level: 1, name: "Piyasa (4.4)" })).toBeVisible();
    await expect(page.getByRole("tab", { name: /Genel bakış/ })).toBeVisible();
    await expect(page.getByText("Sanal kasa").or(page.getByText("Henüz plan yok")).first()).toBeVisible();
  });
});
