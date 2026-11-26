import { useCallback, useState } from "react";
import { Link } from "react-router-dom";
import { getLatestIq } from "../api/iqApi";
import { computePortfolioProposal, getPortfolioOptions, getPortfolioProposal, portfolioSource } from "../api/portfolioApi";
import { useAuth } from "../auth/useAuth";
import Card from "../components/Card";
import EmptyState from "../components/EmptyState";
import ErrorBox from "../components/ErrorBox";
import Notice from "../components/Notice";
import PageHeader from "../components/PageHeader";
import SegmentBadge from "../components/SegmentBadge";
import Spinner from "../components/Spinner";
import ExplainPortfolio from "../components/portfolio/ExplainPortfolio";
import InvestableSteps from "../components/portfolio/InvestableSteps";
import OptionPicker from "../components/portfolio/OptionPicker";
import ProposalView from "../components/portfolio/ProposalView";
import RiskPicker from "../components/portfolio/RiskPicker";
import { missingChoices } from "../components/portfolio/preferences";
import { clampRisk, maxRiskForSegment, riskRank } from "../components/portfolio/risk";
import { ceilingReasons, riskCeiling, serviceCeilingNote } from "../components/portfolio/serviceText";
import { usePreferences } from "../components/portfolio/usePreferences";
import { formatDateTime } from "../lib/format";
import { INSTITUTION_STYLE_LABELS, LEVEL_LABELS, PORTFOLIO_OPTION_LABELS } from "../lib/labels";
import { ROUTES } from "../lib/routes";
import { useAsync } from "../lib/useAsync";
import type { IqResult } from "../types/api";
import "../components/portfolio/portfolio.css";

function ProposalSection({ latestIq }: { latestIq: IqResult }) {
  const proposal = useAsync(useCallback((signal: AbortSignal) => getPortfolioProposal({ signal }), []));

  if (proposal.loading && proposal.data === undefined) return <Spinner layout="block" label="Öneri yükleniyor…" />;
  if (proposal.error) return <ErrorBox title="Öneri yüklenemedi" error={proposal.error} onRetry={proposal.reload} />;
  if (!proposal.data) {
    return (
      <EmptyState
        title="Henüz önerin yok"
        description="Portföy türünü ve risk seviyeni seçtikten sonra Portföy servisi önerini hesaplar."
      />
    );
  }
  return (
    <div className="stack-lg">
      <ProposalView result={proposal.data} latestIq={latestIq} />
      <hr className="divider" />
      <div className="stack-sm">
        <h3 className="proposal-subtitle">Koçun açıklaması</h3>
        <ExplainPortfolio />
      </div>
    </div>
  );
}

function PortfolioContent({ latestIq, userId }: { latestIq: IqResult; userId: string | undefined }) {
  const serviceOptions = useAsync(useCallback((signal: AbortSignal) => getPortfolioOptions({ signal }), []));
  const options = serviceOptions.data ?? null;
  const ceiling = riskCeiling(latestIq.segment, options);
  const unavailable = options?.unavailableOptions ?? [];
  const { preferences: stored, update } = usePreferences(userId);
  // a stored option the service does not offer yet counts as not chosen
  const preferences = stored.option && unavailable.includes(stored.option) ? { ...stored, option: null } : stored;
  const riskLevel = clampRisk(preferences.riskLevel, ceiling);
  const segmentCeiling = maxRiskForSegment(latestIq.segment);
  const lowered = options !== null && riskRank(ceiling) < riskRank(segmentCeiling);
  const missing = missingChoices({ ...preferences, riskLevel });
  const sample = portfolioSource() === "mock";
  const [version, setVersion] = useState(0);
  const [computing, setComputing] = useState(false);
  const [computeError, setComputeError] = useState<unknown>(null);
  const ready = missing.length === 0 && preferences.option !== null && riskLevel !== null;

  async function compute() {
    if (!ready || preferences.option === null || riskLevel === null) return;
    setComputing(true);
    setComputeError(null);
    try {
      await computePortfolioProposal({ ...preferences, option: preferences.option, riskLevel });
      setVersion((v) => v + 1);
    } catch (error) {
      setComputeError(error);
    } finally {
      setComputing(false);
    }
  }

  const chosen = [
    preferences.option ? PORTFOLIO_OPTION_LABELS[preferences.option] : null,
    preferences.option === "INSTITUTION" && preferences.institutionStyle ? INSTITUTION_STYLE_LABELS[preferences.institutionStyle] : null,
    riskLevel ? `${LEVEL_LABELS[riskLevel]} risk` : null,
  ].filter(Boolean);

  return (
    <>
      <Card tone="muted" as="div" className="iq-strip">
        <div className="iq-strip-inner">
          <div className="iq-strip-score">
            <span className="iq-strip-label">Finansal IQ'n</span>
            <span className="iq-strip-value">{latestIq.score}</span>
            <SegmentBadge segment={latestIq.segment} withRange />
          </div>
          <p className="text-sm text-secondary">
            Son hesaplama {formatDateTime(latestIq.updatedAt || latestIq.createdAt)}. Risk tavanın bu skora göre belirlenir.{" "}
            <Link to={ROUTES.profile}>Profili güncelle</Link>
          </p>
        </div>
      </Card>

      <Card title="1. Portföy türünü seç" subtitle="Dört seçenekten birini seç; dağılımı Portföy servisi hesaplar.">
        <OptionPicker
          preferences={preferences}
          onChange={update}
          unavailable={unavailable}
          styleInfo={options?.institutionStyleInfo ?? []}
        />
      </Card>

      {serviceOptions.error ? (
        <ErrorBox title="Portföy seçenekleri yüklenemedi" error={serviceOptions.error} onRetry={serviceOptions.reload} />
      ) : null}

      <Card title="2. Risk seviyeni seç" subtitle="Finansal IQ'n ve finansal durumun, seçebileceğin en yüksek seviyeyi belirler.">
        <RiskPicker
          value={riskLevel}
          ceiling={ceiling}
          onChange={(level) => update({ riskLevel: level })}
          note={lowered ? serviceCeilingNote(latestIq.segment, ceiling) : undefined}
          reasons={ceilingReasons(options)}
        />
      </Card>

      {options ? (
        <Card title="3. Yatırılabilir tutarın" subtitle="Öneriyi hesaplamadan önce, Portföy servisinin bu tutarları nasıl bulduğu adım adım.">
          <InvestableSteps iqScore={options.iqScore} investable={options.investable} />
        </Card>
      ) : null}

      <Notice title={missing.length === 0 ? "Seçimin hazır" : "Seçimin eksik"}>
        <p>
          {missing.length === 0 ? `${chosen.join(" · ")}. ` : `Eksik: ${missing.join(", ")}. `}
          {sample
            ? "Seçimlerin şimdilik yalnızca bu sekmede saklanıyor; Portföy servisi hazır olduğunda ona gönderilecek ve önerin onlara göre hesaplanacak."
            : preferences.option === "AINVEST"
              ? "AInvest önerisi koşullu piyasa planlarıdır; Piyasa (4.4) sayfasında."
              : "Öneriyi hesapla dediğinde seçimin Portföy servisine kaydedilir ve dağılımı servis hesaplar."}
        </p>
        {sample || preferences.option === "AINVEST" ? null : (
          <div className="cluster">
            <button type="button" className="btn btn-primary" onClick={compute} disabled={!ready || computing}>
              {computing ? "Hesaplanıyor…" : "Öneriyi hesapla"}
            </button>
          </div>
        )}
      </Notice>
      {computeError ? <ErrorBox title="Öneri hesaplanamadı" error={computeError} onRetry={compute} /> : null}

      <Card title="Öneri" subtitle={sample ? undefined : "Portföy servisinin hesapladığı son önerin."}>
        {/* a new key after each computed proposal reloads the latest one */}
        <ProposalSection key={version} latestIq={latestIq} />
      </Card>
    </>
  );
}

// Portfolio (CLAUDE.md 8.4): the user picks an option and a risk level up to the IQ ceiling; the Portfolio Service
// computes the allocation and the Coach explains it. Until the service exists the proposal is the schema's sample.
export default function PortfolioPage() {
  const { session } = useAuth();
  const latest = useAsync(useCallback((signal: AbortSignal) => getLatestIq({ signal }), []));

  return (
    <div className="page">
      <PageHeader
        title="Portföy"
        description="Finansal IQ'nu gördükten sonra portföy türünü ve risk seviyeni seç; dağılımı Portföy servisi hesaplar, koç açıklar."
      />
      {latest.loading && latest.data === undefined ? (
        <Spinner layout="block" label="Finansal IQ yükleniyor…" />
      ) : latest.error ? (
        <ErrorBox title="Finansal IQ sonucun yüklenemedi" error={latest.error} onRetry={latest.reload} />
      ) : !latest.data ? (
        <Card>
          <EmptyState
            title="Önce Finansal IQ skorunu hesapla"
            description="Portföy seçenekleri ve risk tavanı Finansal IQ skoruna göre belirlenir. Profilini doldurup skorunu hesapladıktan sonra buraya dön."
            action={
              <Link className="btn btn-primary" to={ROUTES.profile}>
                Profile git
              </Link>
            }
          />
        </Card>
      ) : (
        <PortfolioContent latestIq={latest.data} userId={session?.userId} />
      )}
    </div>
  );
}
