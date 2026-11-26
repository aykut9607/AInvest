import Button from "../Button";
import Card from "../Card";
import { formatDateTime } from "../../lib/format";
import type { SignalAsset } from "../../types/signals";
import { DIRECTION_LABELS, labelOf, zoneText } from "./signalLabels";
import type { WatchItem } from "./watchlist";

export interface WatchlistSectionProps {
  items: WatchItem[];
  persistent: boolean;
  onRemove: (asset: SignalAsset) => void;
}

// the plans the user follows virtually; nothing here is an order
export default function WatchlistSection({ items, persistent, onRemove }: WatchlistSectionProps) {
  return (
    <Card
      title="Sanal takip listem"
      subtitle={
        persistent
          ? "Yalnızca bu tarayıcıda saklanır."
          : "Tarayıcı depolaması kullanılamıyor: liste sayfa yenilenince silinir."
      }
      className="watchlist-card"
    >
      {items.length === 0 ? (
        <p className="text-sm text-muted">
          Henüz takip ettiğin bir plan yok. Bir kartın altındaki “Sanal takibe al” düğmesiyle ekleyebilirsin.
        </p>
      ) : (
        <ul className="watchlist" aria-label="Takip edilen planlar">
          {items.map((item) => (
            <li key={item.asset} className="watchlist-item">
              <div className="watchlist-text">
                <p className="watchlist-name">{item.assetName}</p>
                <p className="text-sm text-secondary">
                  {item.direction && item.entryZone
                    ? `${labelOf(DIRECTION_LABELS, item.direction)} · bölge ${zoneText(item.entryZone, item.quoteCurrency)}`
                    : "Plan yok; piyasa görüşü izleniyor"}
                </p>
                <p className="text-xs text-muted">Eklenme: {formatDateTime(item.addedAt)}</p>
              </div>
              <Button size="sm" variant="ghost" onClick={() => onRemove(item.asset)} aria-label={`${item.assetName}: takipten çıkar`}>
                Takipten çıkar
              </Button>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
