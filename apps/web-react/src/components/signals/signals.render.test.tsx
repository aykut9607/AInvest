import { renderToString as renderRaw } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AuthContext, type AuthContextValue } from "../../auth/useAuth";
import { SAMPLE_SIGNAL_PLANS } from "../../mocks/signalPlans";
import SignalsPage from "../../pages/SignalsPage";
import { MemoryStorage } from "../../test/helpers";
import PlanCard from "./PlanCard";
import WatchlistSection from "./WatchlistSection";
import { WATCHLIST_STORAGE_KEY, addToWatchlist } from "./watchlist";

// server render without the <!-- --> markers React puts between adjacent text nodes
const renderToString = (node: Parameters<typeof renderRaw>[0]) => renderRaw(node).replace(/<!-- -->/g, "");

const plan = (asset: string) => SAMPLE_SIGNAL_PLANS.find((p) => p.asset === asset)!;

afterEach(() => vi.unstubAllGlobals());

describe("PlanCard", () => {
  it("shows an active conditional plan with its levels, models and score against the threshold", () => {
    const html = renderToString(<PlanCard plan={plan("GOLD")} watched={false} onToggleWatch={() => {}} />);
    // no "Örnek veri" badge in the web UI (product decision, 25 Nov)
    expect(html).not.toContain("Örnek veri");
    expect(html).toContain("Plan aktif");
    expect(html).toContain('aria-valuenow="76"');
    expect(html).toContain("Eşik 70");
    expect(html).toContain("Altın 4.300 bölgesine gelirse");
    expect(html).toContain("4.280–4.320 USD");
    expect(html).toContain("Kısa (short)");
    expect(html).toContain("SFP (likidite avı), RSI uyumsuzluğu");
    expect(html).toContain("Geçersizlik");
    expect(html).toContain("4.400 USD");
    expect(html).toContain("Mikro geçersizlik");
    expect(html).toContain("Kilit seviye");
    expect(html).toContain("Ana model");
    expect(html).toContain("Alternatif");
    expect(html).toContain("Sanal takibe al");
  });

  it("shows a waiting asset without a plan and the remove button when watched", () => {
    const html = renderToString(<PlanCard plan={plan("SPX")} watched onToggleWatch={() => {}} />);
    expect(html).toContain("Onay bekleniyor");
    expect(html).toContain("Şu an koşullu plan yok.");
    expect(html).toContain("Alternatif model yok.");
    expect(html).toContain("Takipten çıkar");
    expect(html).toContain('aria-pressed="true"');
  });
});

describe("WatchlistSection", () => {
  it("lists followed plans with the date added, and says when storage is not available", () => {
    const items = addToWatchlist([], plan("BTC"), new Date("2026-11-24T10:00:00Z"));
    const html = renderToString(<WatchlistSection items={items} persistent={false} onRemove={() => {}} />);
    expect(html).toContain("Bitcoin (BTCUSDT)");
    expect(html).toContain("Uzun (long) · bölge 86.500–88.000 USD");
    expect(html).toContain("Eklenme: 24 Kasım 2026 13:00");
    expect(html).toContain("liste sayfa yenilenince silinir");

    expect(renderToString(<WatchlistSection items={[]} persistent onRemove={() => {}} />)).toContain("Henüz takip ettiğin bir plan yok.");
  });
});

describe("SignalsPage", () => {
  it("shows the plans without notice or disclaimer lines and restores the watchlist from localStorage", () => {
    const storage = new MemoryStorage();
    storage.setItem(`${WATCHLIST_STORAGE_KEY}.u-1`, JSON.stringify(addToWatchlist([], plan("GOLD"), new Date("2026-11-24T10:00:00Z"))));
    vi.stubGlobal("localStorage", storage);
    const auth = { session: { userId: "u-1", email: "demo.medium@ainvest.local", accessToken: "a", refreshToken: "r" } } as AuthContextValue;

    const html = renderToString(
      <MemoryRouter>
        <AuthContext.Provider value={auth}>
          <SignalsPage />
        </AuthContext.Provider>
      </MemoryRouter>
    );
    expect(html).not.toContain("tavsiyesi değildir");
    expect(html).not.toContain("emir verilmez");
    expect(html).not.toContain("Güven metinleri geçici");
    expect(html).not.toContain("Örnek veri");
    expect(html).toContain("Sanal takip listem");
    expect(html).toContain("Altın (COMEX vadeli, GC=F)");
  });
});
