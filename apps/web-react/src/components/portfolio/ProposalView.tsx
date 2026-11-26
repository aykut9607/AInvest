import Badge from "../Badge";
import Notice from "../Notice";
import SegmentBadge from "../SegmentBadge";
import type { PortfolioProposalResult } from "../../api/portfolioApi";
import { formatDateTime, formatMoney, formatPercent } from "../../lib/format";
import {
  APPLIED_RULE_LABELS,
  INSTITUTION_STYLE_LABELS,
  LEVEL_LABELS,
  PORTFOLIO_OPTION_LABELS,
  assetLabel,
  capitalizeTr,
} from "../../lib/labels";
import type { IqResult, PortfolioProposal } from "../../types/api";
import AllocationChart from "./AllocationChart";
import { isProposalStale, reasonText } from "./proposal";
import { formatPeriod, safeUrl } from "./serviceText";

function preferenceSummary(preferences: PortfolioProposal["preferences"]): string {
  const parts = [PORTFOLIO_OPTION_LABELS[preferences.option] ?? preferences.option];
  if (preferences.institutionStyle) parts.push(INSTITUTION_STYLE_LABELS[preferences.institutionStyle] ?? preferences.institutionStyle);
  parts.push(`${LEVEL_LABELS[preferences.riskLevel] ?? preferences.riskLevel} risk`);
  if (preferences.focusAssets?.length) parts.push(`odak: ${preferences.focusAssets.map(assetLabel).join(", ")}`);
  if (preferences.excludedAssets?.length) parts.push(`istenmeyen: ${preferences.excludedAssets.map(assetLabel).join(", ")}`);
  return parts.join(" · ");
}

export interface ProposalViewProps {
  result: PortfolioProposalResult;
  latestIq: IqResult | null;
}

// Shows a proposal exactly as the Portfolio Service (or the draft schema's sample) computed it.
export default function ProposalView({ result, latestIq }: ProposalViewProps) {
  const { proposal, source } = result;
  const sample = source === "mock";
  const stale = isProposalStale(proposal, latestIq, source);
  const { basedOn, risk, investable } = proposal;

  return (
    <div className="stack-lg">
      {stale ? (
        <Notice tone="warning" title="Önerin eski bir skora dayanıyor">
          Finansal IQ'n bu öneri hazırlandıktan sonra yeniden hesaplandı. Güncel bir öneri oluşturmadan bu dağılımı kullanma.
        </Notice>
      ) : null}

      <div className="grid grid-2">
        <section className="proposal-block" aria-label="Önerinin dayandığı skor">
          <h3 className="proposal-subtitle">Dayandığı Finansal IQ</h3>
          <dl className="kv text-sm">
            <dt>Skor</dt>
            <dd>{basedOn.iqScore}</dd>
            <dt>Segment</dt>
            <dd>
              <SegmentBadge segment={basedOn.segment} />
            </dd>
            <dt>Hesaplandığı tarih</dt>
            <dd>{formatDateTime(basedOn.iqCalculatedAt)}</dd>
            <dt>Skor kuralı sürümü</dt>
            <dd>{basedOn.scoringVersion}</dd>
            {basedOn.appliedRule ? (
              <>
                <dt>Uygulanan kural</dt>
                <dd>{APPLIED_RULE_LABELS[basedOn.appliedRule]?.title ?? basedOn.appliedRule}</dd>
              </>
            ) : null}
          </dl>
        </section>

        <section className="proposal-block" aria-label="Risk">
          <h3 className="proposal-subtitle">Risk</h3>
          <dl className="kv text-sm">
            <dt>Seçilen</dt>
            <dd>{capitalizeTr(LEVEL_LABELS[risk.chosen] ?? risk.chosen)}</dd>
            <dt>İzin verilen en yüksek</dt>
            <dd>{capitalizeTr(LEVEL_LABELS[risk.maxAllowed] ?? risk.maxAllowed)}</dd>
          </dl>
          <p className="text-xs text-muted">
            {sample ? "Seçimler: " : "Seçimlerin: "}
            {preferenceSummary(proposal.preferences)}
          </p>
        </section>
      </div>

      <section aria-label="Yatırılabilir tutar">
        <h3 className="proposal-subtitle">Yatırılabilir</h3>
        <div className="stat-row">
          <div className="stat-tile">
            <span className="stat-label">Yatırılabilir pay</span>
            <span className="stat-value">{formatPercent(investable.sharePercent)}</span>
          </div>
          <div className="stat-tile">
            <span className="stat-label">Her ay</span>
            <span className="stat-value">{formatMoney(investable.monthlyAmount)}</span>
          </div>
          <div className="stat-tile">
            <span className="stat-label">Tek seferlik</span>
            <span className="stat-value">{formatMoney(investable.oneTimeAmount)}</span>
          </div>
        </div>
        <p className="text-xs text-muted proposal-note">
          Pay, aylık artana ve 3 aylık acil durum fonunun üstündeki nakde uygulanır. Hesabı Portföy servisi yapar.
        </p>
      </section>

      <section aria-label="Dağılım">
        <h3 className="proposal-subtitle">Dağılım</h3>
        <AllocationChart allocations={proposal.allocations} monthlyAmount={investable.monthlyAmount} />
      </section>

      {proposal.reasons.length > 0 ? (
        <section aria-label="Gerekçeler">
          <h3 className="proposal-subtitle">Gerekçeler</h3>
          <ul className="proposal-reasons">
            {proposal.reasons.map((code) => {
              const reason = reasonText(code);
              return (
                <li key={code}>
                  {reason.raw ? (
                    <>
                      <code>{reason.text}</code> <span className="text-xs text-muted">(açıklaması henüz yok)</span>
                    </>
                  ) : (
                    reason.text
                  )}
                </li>
              );
            })}
          </ul>
        </section>
      ) : null}

      {proposal.source?.name ? (
        <p className="text-sm proposal-source">
          Kaynak:{" "}
          {safeUrl(proposal.source.url) ? (
            <a href={safeUrl(proposal.source.url) ?? undefined} target="_blank" rel="noreferrer">
              {proposal.source.name}
            </a>
          ) : (
            proposal.source.name
          )}
          {proposal.source.period ? `, ${formatPeriod(proposal.source.period)}` : null}
        </p>
      ) : null}

      <div className="cluster">
        {sample ? null : <Badge tone="info">Portföy servisi</Badge>}
        <span className="text-xs text-muted">Öneri tarihi {formatDateTime(proposal.createdAt)}</span>
      </div>
    </div>
  );
}
