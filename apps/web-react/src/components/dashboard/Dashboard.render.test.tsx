import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import DashboardPage from "../../pages/DashboardPage";
import type { DashboardLocationState } from "../../lib/routes";
import type { DebtPayoffResult } from "../../api/financeApi";
import { DebtPayoffBody } from "./DebtPayoffCard";
import FactorBreakdownCard from "./FactorBreakdownCard";
import { TrendView } from "./TrendCard";
import { AlertList } from "./WarningsCard";
import { BREAKDOWN, TREND, payoffFor } from "./testFixtures";

// Server rendering, no browser: effects (API calls) do not run, so the page shows what it can without the network.

function renderPage(state?: DashboardLocationState | Record<string, unknown>): string {
  return renderToString(
    <MemoryRouter initialEntries={[{ pathname: "/panel", state }]}>
      <DashboardPage />
    </MemoryRouter>
  );
}

const count = (html: string, needle: string) => html.split(needle).length - 1;

describe("DashboardPage", () => {
  it("shows the result from the profile page at once: score, segment, five factor bars, the Coach button", () => {
    const html = renderPage({ calculation: { score: 92, segment: "HIGH", factorBreakdown: BREAKDOWN } });
    expect(html).toContain('data-testid="score-value">92<');
    expect(html).toContain("YÜKSEK");
    expect(html).toContain(" · 71–100");
    expect(html).toContain("Finansal durum güçlü.");
    expect(html).toContain("Az önce hesaplandı");
    expect(html).toContain("Skorun güncellendi");
    expect(count(html, 'data-testid="factor-bar"')).toBe(5);
    expect(count(html, 'role="meter"')).toBe(5);
    expect(html).toContain("Nakit rezervi");
    expect(html).toContain("Skorumu açıkla");
    // the other cards load on their own (their calls start after mounting)
    expect(html).toContain("Uyarılar yükleniyor");
    expect(html).toContain("Skor geçmişi yükleniyor");
    expect(html).toContain("Borç ödeme planı hesaplanıyor");
    // no rule card without appliedRule
    expect(html).not.toContain("Bu skor nasıl belirlendi?");
  });

  it("explains a rule-set score with the rule card", () => {
    const html = renderPage({
      calculation: {
        score: 100,
        segment: "HIGH",
        factorBreakdown: { ...BREAKDOWN, factors: { ...BREAKDOWN.factors, ExpenseRatio: 15, Impatience: 10 }, appliedRule: "VERY_HIGH_WEALTH" },
      },
    });
    expect(html).toContain("Bu skor nasıl belirlendi?");
    expect(html).toContain("Çok yüksek servet kuralı");
    expect(html).toContain("en az 10.000.000");
  });

  it("waits for /latest without route state, and ignores a foreign state", () => {
    expect(renderPage()).toContain("Hazırlanıyor");
    expect(renderPage({ from: "/asistan" })).toContain("Hazırlanıyor");
  });
});

describe("FactorBreakdownCard", () => {
  it("shows points / max with a level for screen readers", () => {
    const html = renderToString(<FactorBreakdownCard breakdown={BREAKDOWN} score={92} />);
    expect(html).toContain("9 / 15");
    expect(html).toContain('aria-valuetext="9 / 15 puan, orta"');
    expect(html).toContain('aria-valuetext="25 / 25 puan, güçlü"');
    expect(html).toContain('data-tone="warning"');
  });

  it("shows an unknown factor with its points only", () => {
    const html = renderToString(
      <FactorBreakdownCard breakdown={{ version: "v3", factors: { NewFactor: 4 }, warnings: [] }} score={4} />
    );
    expect(html).toContain("NewFactor");
    expect(html).toContain("4 puan");
    expect(html).not.toContain('role="meter"');
  });

  it("says when there is no breakdown", () => {
    expect(renderToString(<FactorBreakdownCard breakdown={null} score={50} />)).toContain("faktör dökümü yok");
  });
});

describe("TrendView", () => {
  it("draws one marker per calculation with the last score as end label", () => {
    const html = renderToString(
      <MemoryRouter>
        <TrendView points={TREND} showTable={false} />
      </MemoryRouter>
    );
    expect(count(html, 'data-testid="trend-point"')).toBe(4);
    expect(html).toContain("ilk skor 8, son skor 92");
    expect(html).toContain(">92</text>");
    expect(html).toContain("DÜŞÜK 0–40");
  });

  it("shows the same values as a table", () => {
    const html = renderToString(
      <MemoryRouter>
        <TrendView points={TREND} showTable />
      </MemoryRouter>
    );
    expect(html).toContain('data-testid="trend-table"');
    expect(count(html, "<tr>")).toBe(5);
    expect(html).toContain(">–</td>");
    expect(html).toContain(">+29</td>");
    expect(html).toContain(">63,7</td>");
  });

  it("asks for a second calculation when there is only one", () => {
    const html = renderToString(
      <MemoryRouter>
        <TrendView points={TREND.slice(0, 1)} showTable={false} />
      </MemoryRouter>
    );
    expect(html).toContain("en az iki hesaplama");
    expect(html).toContain("skor 8");
    expect(html).not.toContain("trend-point");
  });
});

describe("AlertList", () => {
  it("lists the most severe first", () => {
    const html = renderToString(
      <AlertList
        alerts={[
          { code: "HIGH_IMPATIENCE", severity: "INFO", message: "Sabırsızlık yüksek." },
          { code: "MONTHLY_DEFICIT", severity: "CRITICAL", message: "Her ay açık veriyorsun." },
        ]}
      />
    );
    expect(html.indexOf("KRİTİK")).toBeLessThan(html.indexOf("BİLGİ"));
    expect(html.indexOf("Her ay açık")).toBeLessThan(html.indexOf("Sabırsızlık"));
  });

  it("is calm when there is nothing to warn about", () => {
    expect(renderToString(<AlertList alerts={[]} />)).toContain("Önemli bir uyarı yok");
  });
});

describe("DebtPayoffBody", () => {
  const render = (result: DebtPayoffResult, showTable = false) =>
    renderToString(<DebtPayoffBody result={result} showTable={showTable} />);

  it("shows months, totals and the balance chart for a debt that gets paid off", () => {
    const payoff = payoffFor(30000, 3000, 0.035);
    const html = render({ payoff, message: "" });
    expect(payoff.months).toBe(13);
    expect(html).toContain("13 ay (1 yıl 1 ay)");
    expect(html).toContain("30.000 TL");
    expect(html).toContain("%3,5");
    expect(html).toContain("Kalan borç grafiği");
    expect(html).toContain(">Bugün</text>");
  });

  it("switches to the schedule table", () => {
    const html = render({ payoff: payoffFor(6000, 3000, 0), message: "" }, true);
    expect(html).toContain('data-testid="debt-table"');
    expect(count(html, "<tr>")).toBe(3);
  });

  it("explains why a debt is not paid off", () => {
    const payoff = { ...payoffFor(100000, 1000, 0.035), paidOff: false, months: null, schedule: [], totalInterest: 0, totalPaid: 0 };
    const html = render({ payoff, message: "Aylık taksit aylık faizi karşılamıyor; bu yüzden borç hiç azalmıyor." });
    expect(html).toContain("Bu taksitle borç kapanmıyor");
    expect(html).toContain("faizi karşılamıyor");
    expect(html).not.toContain("Kalan borç grafiği");
  });

  it("is short when there is no debt", () => {
    const payoff = { ...payoffFor(0, 0, 0.035), months: 0 };
    expect(render({ payoff, message: "Ödenecek borç yok." })).toContain("Borcun yok");
  });
});
