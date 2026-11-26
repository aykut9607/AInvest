import { useId } from "react";
import { Link } from "react-router-dom";
import { INSTITUTION_STYLE_LABELS, PORTFOLIO_OPTION_LABELS, assetLabel } from "../../lib/labels";
import { ROUTES } from "../../lib/routes";
import type { PortfolioOption } from "../../types/api";
import type { InstitutionStyleInfo } from "../../types/portfolioService";
import { AINVEST_UNAVAILABLE_NOTE, UNAVAILABLE_OPTION_NOTE, formatPeriod, safeUrl } from "./serviceText";
import { FOCUS_ASSETS, INSTITUTION_STYLES, OPTIONS, STANDARD_BASKET, toggleAsset, type PortfolioPreferences } from "./preferences";

export interface OptionPickerProps {
  preferences: PortfolioPreferences;
  onChange: (next: Partial<PortfolioPreferences>) => void;
  // options the Portfolio Service lists as not selectable yet (shown, disabled)
  unavailable?: PortfolioOption[];
  // the service's names, descriptions and sources of the institution styles (4.1)
  styleInfo?: InstitutionStyleInfo[];
}

function AssetChecklist({
  legend,
  hint,
  assets,
  selected,
  onToggle,
}: {
  legend: string;
  hint: string;
  assets: string[];
  selected: string[];
  onToggle: (asset: string) => void;
}) {
  return (
    <fieldset className="asset-checklist">
      <legend className="field-label">{legend}</legend>
      <p className="field-hint">{hint}</p>
      <div className="asset-chips">
        {assets.map((asset) => (
          <label key={asset} className="asset-chip">
            <input type="checkbox" checked={selected.includes(asset)} onChange={() => onToggle(asset)} />
            <span>{assetLabel(asset)}</span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}

// Step 1: the four portfolio options as selectable cards, plus the details the chosen option needs.
function StyleSource({ info }: { info: InstitutionStyleInfo }) {
  const url = safeUrl(info.source.url);
  const period = formatPeriod(info.source.period);
  return (
    <span className="option-style-source">
      Kaynak:{" "}
      {url ? (
        <a href={url} target="_blank" rel="noreferrer">
          {info.source.name}
        </a>
      ) : (
        info.source.name
      )}
      {period ? `, ${period}` : null}
    </span>
  );
}

export default function OptionPicker({ preferences, onChange, unavailable = [], styleInfo = [] }: OptionPickerProps) {
  const name = useId();
  const styleName = useId();
  const { option } = preferences;

  return (
    <div className="stack">
      <fieldset className="option-picker">
        <legend className="field-label">Portföy türü</legend>
        <div className="option-grid">
          {OPTIONS.map((info) => {
            const locked = unavailable.includes(info.value);
            return (
              <label key={info.value} className={`option-card${locked ? " is-locked" : ""}`}>
                <input
                  type="radio"
                  name={name}
                  value={info.value}
                  checked={!locked && option === info.value}
                  disabled={locked}
                  onChange={() => onChange({ option: info.value })}
                />
                <span className="option-card-body">
                  <span className="option-card-code">{info.code}</span>
                  <span className="option-card-title">{PORTFOLIO_OPTION_LABELS[info.value]}</span>
                  <span className="option-card-text">{info.description}</span>
                  {locked ? <span className="option-card-note">{UNAVAILABLE_OPTION_NOTE}</span> : null}
                </span>
              </label>
            );
          })}
        </div>
      </fieldset>
      {unavailable.includes("AINVEST") ? (
        <p className="text-sm text-secondary">
          {AINVEST_UNAVAILABLE_NOTE} <Link to={ROUTES.signals}>Piyasa (4.4)</Link> sayfasında.
        </p>
      ) : null}

      {option === "INSTITUTION" ? (
        <div className="option-details">
          <fieldset className="option-styles">
            <legend className="field-label">Kurum tarzı</legend>
            <div className="option-style-list">
              {INSTITUTION_STYLES.map((style) => {
                const info = styleInfo.find((s) => s.code === style.value);
                return (
                  <label key={style.value} className="option-style">
                    <input
                      type="radio"
                      name={styleName}
                      value={style.value}
                      checked={preferences.institutionStyle === style.value}
                      onChange={() => onChange({ institutionStyle: style.value })}
                    />
                    <span>
                      <span className="option-style-title">{info?.label ?? INSTITUTION_STYLE_LABELS[style.value]}</span>
                      <span className="option-style-text">{info?.description ?? style.description}</span>
                      {info ? <StyleSource info={info} /> : null}
                    </span>
                  </label>
                );
              })}
            </div>
          </fieldset>
          {styleInfo.length === 0 ? (
            <p className="text-xs text-muted">
              Dağılım, kurumun kendi yayımladığı fon dağılımından alınır; kaynağı ve dönemi öneride yazar.
            </p>
          ) : null}
        </div>
      ) : null}

      {option === "CUSTOM" ? (
        <div className="option-details">
          <AssetChecklist
            legend="Odaklanmak istediğin alanlar"
            hint="Birden fazla seçebilirsin; en az bir alan gerekli."
            assets={FOCUS_ASSETS}
            selected={preferences.focusAssets}
            onToggle={(asset) => onChange({ focusAssets: toggleAsset(preferences.focusAssets, asset) })}
          />
        </div>
      ) : null}

      {option === "STANDARD" ? (
        <div className="option-details">
          <AssetChecklist
            legend="Sepette istemediğin varlıklar"
            hint="İşaretlediğin varlıkların yerine Portföy servisi bir alternatif koyar (ör. Bitcoin yerine altın)."
            assets={STANDARD_BASKET}
            selected={preferences.excludedAssets}
            onToggle={(asset) => onChange({ excludedAssets: toggleAsset(preferences.excludedAssets, asset) })}
          />
        </div>
      ) : null}

      {option === "AINVEST" && !unavailable.includes("AINVEST") ? (
        <div className="option-details">
          <p className="text-sm">
            AInvest önerisi, kural tabanlı onay puanı eşiği geçen koşullu planlardan oluşur; emir değil, sanal takip içindir.
            Güncel planlar <Link to={ROUTES.signals}>Piyasa (4.4)</Link> sayfasında.
          </p>
        </div>
      ) : null}
    </div>
  );
}
