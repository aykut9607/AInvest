import { useId } from "react";
import { Link } from "react-router-dom";
import { INSTITUTION_STYLE_LABELS, PORTFOLIO_OPTION_LABELS, assetLabel } from "../../lib/labels";
import { ROUTES } from "../../lib/routes";
import { FOCUS_ASSETS, INSTITUTION_STYLES, OPTIONS, STANDARD_BASKET, toggleAsset, type PortfolioPreferences } from "./preferences";

export interface OptionPickerProps {
  preferences: PortfolioPreferences;
  onChange: (next: Partial<PortfolioPreferences>) => void;
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
export default function OptionPicker({ preferences, onChange }: OptionPickerProps) {
  const name = useId();
  const styleName = useId();
  const { option } = preferences;

  return (
    <div className="stack">
      <fieldset className="option-picker">
        <legend className="field-label">Portföy türü</legend>
        <div className="option-grid">
          {OPTIONS.map((info) => (
            <label key={info.value} className="option-card">
              <input
                type="radio"
                name={name}
                value={info.value}
                checked={option === info.value}
                onChange={() => onChange({ option: info.value })}
              />
              <span className="option-card-body">
                <span className="option-card-code">{info.code}</span>
                <span className="option-card-title">{PORTFOLIO_OPTION_LABELS[info.value]}</span>
                <span className="option-card-text">{info.description}</span>
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {option === "INSTITUTION" ? (
        <div className="option-details">
          <fieldset className="option-styles">
            <legend className="field-label">Kurum tarzı</legend>
            <div className="option-style-list">
              {INSTITUTION_STYLES.map((style) => (
                <label key={style.value} className="option-style">
                  <input
                    type="radio"
                    name={styleName}
                    value={style.value}
                    checked={preferences.institutionStyle === style.value}
                    onChange={() => onChange({ institutionStyle: style.value })}
                  />
                  <span>
                    <span className="option-style-title">{INSTITUTION_STYLE_LABELS[style.value]}</span>
                    <span className="option-style-text">{style.description}</span>
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
          <p className="text-xs text-muted">
            Dağılım, kurumun kendi yayımladığı fon dağılımından alınır; kaynağı ve dönemi öneride yazar.
          </p>
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

      {option === "AINVEST" ? (
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
