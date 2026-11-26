import { renderToString as renderRaw } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { SAMPLE_PORTFOLIO_PROPOSAL } from "../../mocks/portfolioProposal";
import type { IqResult } from "../../types/api";
import type { PortfolioOptions } from "../../types/portfolioService";
import InvestableSteps from "./InvestableSteps";
import OptionPicker from "./OptionPicker";
import ProposalView from "./ProposalView";
import RiskPicker from "./RiskPicker";
import { EMPTY_PREFERENCES } from "./preferences";
import { ceilingReasons, riskCeiling, serviceCeilingNote } from "./serviceText";

// server render without the <!-- --> markers React puts between adjacent text nodes
const renderToString = (node: Parameters<typeof renderRaw>[0]) => renderRaw(node).replace(/<!-- -->/g, "");

// Server render (no DOM in this test setup): checks what the components put on screen for given data.

const LATEST: IqResult = {
  id: "r1",
  userId: "u-1",
  score: 62,
  segment: "MEDIUM",
  factorBreakdown: null,
  createdAt: "2026-11-20T08:00:00Z",
  updatedAt: "2026-11-24T08:00:00Z",
};

// demo.low's /options from the real Portfolio Service (26 Nov), trimmed
const OPTIONS: PortfolioOptions = {
  iqScore: 27,
  segment: "LOW",
  maxRisk: "LOW",
  investable: {
    sharePercent: 0,
    monthlyAmount: 0,
    oneTimeAmount: 0,
    basis: {
      monthlyIncome: 30000,
      monthlyExpenses: 25000,
      monthlyDebtPayment: 7000,
      monthlySurplus: -2000,
      cashReserve: 3000,
      investmentAmount: 10000,
      reserve: 8000,
      emergencyFund: 75000,
      freeCash: 0,
      reserveMonths: 3,
    },
    reasons: ["RESERVE_FIRST", "NO_MONTHLY_SURPLUS", "DEBT_FIRST"],
  },
  options: ["INSTITUTION", "CUSTOM", "STANDARD", "AINVEST"],
  unavailableOptions: ["AINVEST"],
  institutionStyles: ["ZIRAAT", "ISBANK", "YAPIKREDI"],
  institutionStyleInfo: [
    {
      code: "ISBANK",
      label: "Çok varlıklı fon sepeti",
      description: "TL borçlanma, TL hisse, yabancı hisse, altın ve eurobond fonlarından oluşan sepet.",
      source: { name: "İş Portföy, risk profili sayfası", period: "2026-11", url: "https://www.isportfoy.com.tr/risk-profili-anketi" },
    },
  ],
  assets: ["TRY_DEPOSIT", "GOLD"],
  assetInfo: [{ code: "GOLD", label: "Altın" }],
  reasons: ["RESERVE_FIRST", "NO_MONTHLY_SURPLUS", "DEBT_FIRST"],
};

function radioTag(html: string, label: string): string {
  return html.match(new RegExp(`<input[^>]*aria-label="${label}[^"]*"[^>]*>`))?.[0] ?? "";
}

describe("RiskPicker", () => {
  it("locks the levels above a MEDIUM ceiling and keeps the rest selectable", () => {
    const html = renderToString(<RiskPicker value="MEDIUM" ceiling="MEDIUM" onChange={() => {}} />);
    expect(radioTag(html, "Yüksek \\(kilitli\\)")).toContain("disabled");
    expect(radioTag(html, "Orta:")).not.toContain("disabled");
    expect(radioTag(html, "Orta:")).toContain("checked");
    expect(radioTag(html, "Düşük:")).not.toContain("disabled");
    expect(html).toContain("IQ segmentin şu an en fazla orta seviyesine izin veriyor; skorun yükseldikçe açılır.");
  });

  it("opens every level for a HIGH ceiling", () => {
    const html = renderToString(<RiskPicker value={null} ceiling="HIGH" onChange={() => {}} />);
    expect(html).not.toContain("kilitli");
    expect(html).not.toContain("disabled");
  });
});

describe("service risk ceiling", () => {
  it("uses the service's maxRisk below the segment, explains it and falls back to the segment without options", () => {
    const options: PortfolioOptions = { ...OPTIONS, segment: "HIGH", maxRisk: "LOW", reasons: [...OPTIONS.reasons, "CEILING_RESERVE"] };
    const ceiling = riskCeiling("HIGH", options);
    expect(ceiling).toBe("LOW");
    expect(riskCeiling("HIGH", null)).toBe("HIGH");
    const reasons = ceilingReasons(options);
    // the investable reasons are shown with the investable steps, not under the risk levels
    expect(reasons).toEqual(["Risk tavanın düşük: acil durum fonun 3 aylık giderini karşılamıyor."]);

    const html = renderToString(
      <RiskPicker value="LOW" ceiling={ceiling} onChange={() => {}} note={serviceCeilingNote("HIGH", ceiling)} reasons={reasons} />
    );
    expect(radioTag(html, "Yüksek \\(kilitli\\)")).toContain("disabled");
    expect(radioTag(html, "Orta \\(kilitli\\)")).toContain("disabled");
    expect(radioTag(html, "Düşük:")).not.toContain("disabled");
    expect(html).toContain("IQ segmentin yüksek, ama risk tavanın şu an düşük");
    expect(html).toContain("Risk tavanın düşük: acil durum fonun 3 aylık giderini karşılamıyor.");
  });
});

describe("InvestableSteps", () => {
  it("shows the service's basis step by step and the investable reasons", () => {
    const html = renderToString(<InvestableSteps iqScore={OPTIONS.iqScore} investable={OPTIONS.investable} />);
    for (const text of ["30.000 TL", "25.000 TL", "7.000 TL", "-2.000 TL", "75.000 TL", "8.000 TL", "3.000 TL", "Finansal IQ&#x27;n 27", "3 aylık gider"]) {
      expect(html).toContain(text);
    }
    expect(html).toContain("her ay 0 TL");
    expect(html).toContain("tek seferlik 0 TL");
    expect(html).toContain("Önce 3 aylık acil durum fonunu tamamla");
    expect(html).toContain("Aylık artan paran yok.");
  });

  it("shows only the amounts when the service sends no basis", () => {
    const html = renderToString(<InvestableSteps iqScore={62} investable={{ sharePercent: 32, monthlyAmount: 3200, oneTimeAmount: 0 }} />);
    expect(html).toContain("%32");
    expect(html).toContain("3.200 TL");
    expect(html).not.toContain("Aylık artı");
  });
});

describe("OptionPicker", () => {
  it("disables the options the service does not offer yet and shows the institutions' sources", () => {
    const html = renderToString(
      <MemoryRouter>
        <OptionPicker
          preferences={{ ...EMPTY_PREFERENCES, option: "INSTITUTION" }}
          onChange={() => {}}
          unavailable={OPTIONS.unavailableOptions}
          styleInfo={OPTIONS.institutionStyleInfo}
        />
      </MemoryRouter>
    );
    const ainvest = html.match(/<input[^>]*value="AINVEST"[^>]*>/)?.[0] ?? "";
    expect(ainvest).toContain("disabled");
    expect(html.match(/<input[^>]*value="CUSTOM"[^>]*>/)?.[0]).not.toContain("disabled");
    expect(html).toContain("Henüz seçilemiyor.");
    expect(html).toContain('href="/piyasa"');
    expect(html).toContain("Çok varlıklı fon sepeti");
    expect(html).toContain('href="https://www.isportfoy.com.tr/risk-profili-anketi"');
    expect(html).toContain("İş Portföy, risk profili sayfası");
    expect(html).toContain("Kasım 2026");
  });

  it("shows the four options and the details of the chosen one", () => {
    const render = (option: (typeof EMPTY_PREFERENCES)["option"]) =>
      renderToString(
        <MemoryRouter>
          <OptionPicker preferences={{ ...EMPTY_PREFERENCES, option }} onChange={() => {}} />
        </MemoryRouter>
      );
    const none = render(null);
    for (const code of ["4.1", "4.2", "4.3", "4.4"]) expect(none).toContain(code);
    expect(none).not.toContain("Kurum tarzı</legend>");

    expect(render("INSTITUTION")).toContain("Aktif yönetilen değişken fon (Ziraat)");
    expect(render("CUSTOM")).toContain("Odaklanmak istediğin alanlar");
    expect(render("STANDARD")).toContain("Sepette istemediğin varlıklar");
    expect(render("AINVEST")).toContain('href="/piyasa"');
  });
});

describe("ProposalView", () => {
  it("shows the sample proposal with its allocation table and reasons, without sample or disclaimer lines", () => {
    const html = renderToString(<ProposalView result={{ proposal: SAMPLE_PORTFOLIO_PROPOSAL, source: "mock" }} latestIq={LATEST} />);
    // no "Örnek veri" badge or notice in the web UI (product decision, 25 Nov)
    expect(html).not.toContain("Örnek veri");
    expect(html).not.toContain("demo.high");
    expect(html).toContain("%58");
    expect(html).toContain("5.800 TL");
    expect(html).toContain("3.480 TL");
    for (const cell of ["Altın", "TL mevduat", "S&amp;P 500 endeksi", "Euro", "Nvidia hissesi", "%30", "1.740 TL"]) {
      expect(html).toContain(cell);
    }
    expect(html).toContain("İstemediğin Bitcoin yerine Altın kondu.");
    expect(html).not.toContain("tavsiyesi değildir");
    // the sample is never compared with the user's own IQ
    expect(html).not.toContain("Önerin eski bir skora dayanıyor");
  });

  it("warns about a service proposal based on an older IQ and shows unknown reasons raw", () => {
    const proposal = { ...SAMPLE_PORTFOLIO_PROPOSAL, reasons: ["FUTURE_REASON"] };
    const html = renderToString(<ProposalView result={{ proposal, source: "service" }} latestIq={{ ...LATEST, score: 88, updatedAt: "2026-11-30T08:00:00Z" }} />);
    expect(html).toContain("Önerin eski bir skora dayanıyor");
    expect(html).not.toContain("demo.high profiline");
    expect(html).toContain("<code>FUTURE_REASON</code>");
  });

  it("names the published allocation's source with its link and period", () => {
    const proposal = {
      ...SAMPLE_PORTFOLIO_PROPOSAL,
      source: { name: "Yapı Kredi, Varlık Dağılım Önerileri", period: "2026-10", url: "https://yapikredi.com.tr/x" },
    };
    const html = renderToString(<ProposalView result={{ proposal, source: "service" }} latestIq={null} />);
    expect(html).toContain('Kaynak: <a href="https://yapikredi.com.tr/x"');
    expect(html).toContain("Yapı Kredi, Varlık Dağılım Önerileri</a>, Ekim 2026");
  });
});
