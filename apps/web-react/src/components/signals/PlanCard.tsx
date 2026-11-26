import Badge from "../Badge";
import Button from "../Button";
import Card from "../Card";
import { formatDateTime, formatPrice } from "../../lib/format";
import type { SignalPlan, WaveModel } from "../../types/signals";
import ConfirmationMeter, { ConfirmationBreakdown } from "./ConfirmationMeter";
import {
  BIAS_LABELS,
  DIRECTION_LABELS,
  LTF_SIGNAL_LABELS,
  MODEL_KIND_LABELS,
  isPlanActive,
  labelOf,
  timeframesText,
  zoneText,
} from "./signalLabels";

function ModelBlock({ title, model }: { title: string; model: WaveModel }) {
  return (
    <div className="signal-model">
      <p className="signal-model-title">
        <span className="text-muted">{title}:</span> {model.name}
      </p>
      <p className="text-sm text-secondary">{model.description}</p>
      <p className="text-xs text-muted">
        {labelOf(MODEL_KIND_LABELS, model.kind)} · Uyum {model.fit}/100
      </p>
    </div>
  );
}

export interface PlanCardProps {
  plan: SignalPlan;
  watched: boolean;
  onToggleWatch: (plan: SignalPlan) => void;
}

// One asset of the 4.4 screen: market view, the conditional plan (never an order), levels, models, the confirmation
// score against its threshold and the backtest's confidence text.
export default function PlanCard({ plan, watched, onToggleWatch }: PlanCardProps) {
  const currency = plan.quoteCurrency;
  const price = (value: number) => formatPrice(value, currency, 2);
  const active = isPlanActive(plan);
  const conditional = plan.plan;

  return (
    <Card
      as="article"
      className="signal-card"
      title={plan.assetName}
      subtitle={`Son fiyat ${price(plan.lastPrice)} · ${formatDateTime(plan.generatedAt)}`}
      footer={
        <div className="signal-card-actions">
          <Button
            variant={watched ? "secondary" : "primary"}
            size="sm"
            aria-pressed={watched}
            onClick={() => onToggleWatch(plan)}
          >
            {watched ? "Takipten çıkar" : "Sanal takibe al"}
          </Button>
        </div>
      }
    >
      <div className="stack">
        <section className="signal-section" aria-label="Piyasa görüşü">
          <div className="cluster">
            <Badge>{labelOf(BIAS_LABELS, plan.view.bias)}</Badge>
            <span className="text-xs text-muted">{timeframesText(plan.view.timeframes)}</span>
          </div>
          <p className="text-sm">{plan.view.summary}</p>
        </section>

        <ConfirmationMeter confirmation={plan.confirmation} />

        {conditional ? (
          <section className="signal-plan" aria-label="Koşullu plan">
            <p className="signal-plan-sentence">{conditional.description}</p>
            <ol className="signal-steps">
              <li>
                <span className="signal-step-label">Bölge</span>
                <span className="tabular">{zoneText(conditional.entryZone, currency)}</span>
              </li>
              <li>
                <span className="signal-step-label">Alt zaman dilimi onayı</span>
                <span>
                  {timeframesText(conditional.ltfConfirmation.timeframes)}:{" "}
                  {conditional.ltfConfirmation.signals.map((s) => labelOf(LTF_SIGNAL_LABELS, s)).join(", ")}
                </span>
              </li>
              <li>
                <span className="signal-step-label">Onay gelirse yön</span>
                <span>{labelOf(DIRECTION_LABELS, conditional.direction)}</span>
              </li>
            </ol>
            <p className="text-xs text-muted">{conditional.ltfConfirmation.description}</p>
            <dl className="kv text-sm">
              <dt>Hedefler</dt>
              <dd>{conditional.targets.map(price).join(" · ")}</dd>
              <dt>Zarar durdur</dt>
              <dd>{price(conditional.stop)}</dd>
            </dl>
          </section>
        ) : (
          <section className="signal-plan signal-plan-empty" aria-label="Koşullu plan">
            <p className="signal-plan-sentence">Şu an koşullu plan yok.</p>
            <p className="text-sm text-secondary">
              {active
                ? "Puan eşiğin üstünde, ancak modül bu varlık için bir plan üretmedi."
                : "Onay puanı eşiğin altında; fiyat bir bölgeye gelip kurallar onay verene kadar yalnızca izlenir."}
            </p>
          </section>
        )}

        <section aria-label="Seviyeler">
          <h3 className="signal-subtitle">Seviyeler</h3>
          <dl className="kv text-sm">
            <dt>Geçersizlik (görüş bozulur)</dt>
            <dd>{price(plan.levels.invalidation)}</dd>
            <dt>Mikro geçersizlik (kurulum iptal)</dt>
            <dd>{price(plan.levels.microInvalidation)}</dd>
            <dt>Kilit seviye</dt>
            <dd>{price(plan.levels.keyLevel)}</dd>
          </dl>
        </section>

        <section className="stack-sm" aria-label="Modeller">
          <h3 className="signal-subtitle">Modeller</h3>
          <ModelBlock title="Ana model" model={plan.mainModel} />
          {plan.alternativeModel ? (
            <ModelBlock title="Alternatif" model={plan.alternativeModel} />
          ) : (
            <p className="text-sm text-muted">Alternatif model yok.</p>
          )}
        </section>

        <section className="signal-backtest" aria-label="Geçmiş test">
          <div className="cluster">
            <h3 className="signal-subtitle">Geçmiş test</h3>
            <Badge tone="info">Geçici</Badge>
          </div>
          <p className="text-sm">{plan.backtest.text}</p>
          <p className="text-xs text-muted">
            Dönem {plan.backtest.period} · {plan.backtest.sampleSize} benzersiz kurulum
          </p>
        </section>

        <details className="signal-details">
          <summary>Onay puanının dökümü</summary>
          <ConfirmationBreakdown confirmation={plan.confirmation} />
        </details>
      </div>
    </Card>
  );
}
