import { renderToString as renderRaw } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { SAMPLE_PORTFOLIO_PROPOSAL } from "../../mocks/portfolioProposal";
import type { IqResult } from "../../types/api";
import OptionPicker from "./OptionPicker";
import ProposalView from "./ProposalView";
import RiskPicker from "./RiskPicker";
import { EMPTY_PREFERENCES } from "./preferences";

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

describe("OptionPicker", () => {
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
});
