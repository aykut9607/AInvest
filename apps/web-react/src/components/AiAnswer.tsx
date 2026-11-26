import { fallbackReasonLabel } from "../lib/labels";
import type { AiTextMeta, FallbackReason } from "../types/api";
import Badge, { type BadgeTone } from "./Badge";

export interface AiAnswerProps {
  // explanation / answer text from the AI response
  text: string;
  // the common fields of every AI text response (disclaimer, model, numbersVerified, fallbackUsed, fallbackReason)
  meta: AiTextMeta;
  // optional heading above the text (h3)
  title?: string;
}

// a template answer for these reasons is the intended behaviour, not a failure
const EXPECTED_FALLBACKS: FallbackReason[] = ["NO_BREAKDOWN", "NO_DATA", "BLOCKED_INPUT", "UNSUPPORTED"];

// Renders an AI text with its provenance: which model wrote it, whether the numbers were verified against the data,
// and a "Şablon cevap" badge when the deterministic template was shown instead of the model's text. The response's
// disclaimer is not shown (product decision, 25 Nov: no disclaimer lines in the web UI).
export default function AiAnswer({ text, meta, title }: AiAnswerProps) {
  const paragraphs = text
    .split(/\n{2,}|\n/)
    .map((part) => part.trim())
    .filter(Boolean);
  const reason = meta.fallbackReason;
  const fallbackTone: BadgeTone = reason && EXPECTED_FALLBACKS.includes(reason) ? "info" : "warning";

  return (
    <div className="ai-answer" data-testid="ai-answer">
      {title ? <h3>{title}</h3> : null}
      <div className="ai-answer-meta">
        {meta.fallbackUsed ? (
          <Badge tone={fallbackTone} dot title="Modelin cevabı yerine kodun ürettiği sabit cevap gösterildi.">
            Şablon cevap{reason ? `: ${fallbackReasonLabel(reason)}` : ""}
          </Badge>
        ) : null}
        {meta.model ? <Badge title="Cevabı yazan model">Model: {meta.model}</Badge> : null}
        {meta.numbersVerified ? (
          <Badge tone="good" dot title="Metindeki her sayı hesaplanan veride de var.">
            Sayılar doğrulandı
          </Badge>
        ) : null}
      </div>
      <div className="ai-answer-text">
        {paragraphs.map((paragraph, index) => (
          <p key={index}>{paragraph}</p>
        ))}
      </div>
    </div>
  );
}
