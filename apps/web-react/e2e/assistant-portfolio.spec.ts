import { expect, test } from "@playwright/test";
import { openFromMenu, signInToDashboard } from "./helpers.ts";

// Needs the running stack (Identity, Finance Profile, Financial IQ, AI/RAG, Edge Gateway, `npm run dev`) and the demo
// accounts from `python infra/seed/seed_demo_users.py`. Ollama is optional: without it the assistant answers with its
// deterministic template, which is still an answer. Run: npm run e2e.
// One test, one sign-in: the gateway allows 5 logins a minute per IP and auth-profile.spec.ts uses some of them.

// LOW under both scoring versions (v2: 8, v3: 27); demo.medium is MEDIUM under v2 but HIGH (71) under v3
const DEMO_EMAIL = "demo.low@ainvest.local";

test("demo.low: assistant answers, portfolio respects the IQ risk ceiling, 4.4 watchlist survives a reload", async ({ page }) => {
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

  await test.step("4.4: three plan cards, one added to the virtual watchlist stays after a reload", async () => {
    await openFromMenu(page, "Piyasa (4.4)", /\/piyasa$/);
    // start from an empty list, whatever an earlier run left behind
    await page.evaluate(() => {
      Object.keys(localStorage)
        .filter((key) => key.startsWith("ainvest.signals.watchlist"))
        .forEach((key) => localStorage.removeItem(key));
    });
    await page.reload();

    const cards = page.locator("article.signal-card");
    await expect(cards).toHaveCount(3);

    const gold = cards.filter({ hasText: "Altın (COMEX vadeli, GC=F)" });
    await gold.getByRole("button", { name: "Sanal takibe al" }).click();
    await expect(gold.getByRole("button", { name: "Takipten çıkar" })).toBeVisible();
    await expect(page.getByRole("list", { name: "Takip edilen planlar" })).toContainText("Altın (COMEX vadeli, GC=F)");

    await page.reload();
    const watchlist = page.getByRole("list", { name: "Takip edilen planlar" });
    await expect(watchlist).toContainText("Altın (COMEX vadeli, GC=F)");
    await expect(watchlist).toContainText("Eklenme:");

    // leave the browser state as it was
    await watchlist.getByRole("button", { name: "Altın (COMEX vadeli, GC=F): takipten çıkar" }).click();
    await expect(page.getByText("Henüz takip ettiğin bir plan yok.")).toBeVisible();
  });
});
