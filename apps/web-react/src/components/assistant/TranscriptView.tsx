import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import AiAnswer from "../AiAnswer";
import Badge from "../Badge";
import Button from "../Button";
import { ROUTES } from "../../lib/routes";
import type { AssistantEntry, ErrorEntry, TranscriptEntry, UserEntry } from "./transcript";
import { MODE_LABELS, answerNote, formatTime, intentLabel } from "./assistantLabels";

function UserBubble({ entry }: { entry: UserEntry }) {
  return (
    <li className="chat-row chat-row-user">
      <div className="chat-bubble chat-bubble-user">
        <p className="visually-hidden">Sen:</p>
        <p className="chat-text">{entry.text}</p>
        <p className="chat-time">{formatTime(entry.at)}</p>
      </div>
    </li>
  );
}

function AssistantBubble({ entry }: { entry: AssistantEntry }) {
  const { response } = entry;
  const note = answerNote(response);
  return (
    <li className="chat-row chat-row-assistant">
      <div className="chat-bubble chat-bubble-assistant">
        <p className="visually-hidden">Asistan:</p>
        {/* no disclaimer line in the web UI (product decision, 25 Nov) */}
        <AiAnswer text={response.answer} meta={{ ...response, disclaimer: "" }} />
        {note ? (
          <p className={`chat-note chat-note-${note.tone}`}>
            {note.text}
            {response.intents.includes("MARKET_PRICE") ? (
              <>
                {" "}
                <Link to={ROUTES.signals}>Piyasa (4.4)</Link>
              </>
            ) : null}
          </p>
        ) : null}
        <div className="chat-footer">
          {response.intents.length > 0 ? (
            <ul className="chat-intents" aria-label="Cevabın konuları">
              {response.intents.map((intent) => (
                <li key={intent}>
                  <Badge>{intentLabel(intent)}</Badge>
                </li>
              ))}
            </ul>
          ) : null}
          <span className="chat-time">
            {MODE_LABELS[response.mode] ?? response.mode} · {formatTime(entry.at)}
          </span>
        </div>
      </div>
    </li>
  );
}

function ErrorBubble({ entry, onRetry, disabled }: { entry: ErrorEntry; onRetry?: (question: string) => void; disabled: boolean }) {
  return (
    <li className="chat-row chat-row-assistant">
      <div className="chat-bubble chat-bubble-error" role="alert">
        <p className="chat-error-title">Cevap alınamadı</p>
        <p className="chat-text">{entry.message}</p>
        {onRetry && entry.question ? (
          <div>
            <Button size="sm" onClick={() => onRetry(entry.question)} disabled={disabled}>
              Tekrar sor
            </Button>
          </div>
        ) : null}
      </div>
    </li>
  );
}

export interface TranscriptViewProps {
  entries: TranscriptEntry[];
  pending: boolean;
  onRetry?: (question: string) => void;
}

// the conversation; new entries are announced politely and scrolled into view
export default function TranscriptView({ entries, pending, onRetry }: TranscriptViewProps) {
  const endRef = useRef<HTMLDivElement>(null);
  // entries already on screen; a transcript restored on load does not scroll the page
  const shownCount = useRef(entries.length);
  const count = entries.length;
  const last = entries[count - 1];

  useEffect(() => {
    const grew = count > shownCount.current;
    shownCount.current = count;
    if (!grew && !pending) return;
    const reduced = typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    endRef.current?.scrollIntoView?.({ block: "nearest", behavior: reduced ? "auto" : "smooth" });
  }, [count, pending]);

  return (
    <div className="chat-log-wrap">
      <ol className="chat-log" aria-label="Asistanla konuşma" aria-live="polite" aria-busy={pending || undefined}>
        {entries.map((entry) => {
          if (entry.role === "user") return <UserBubble key={entry.id} entry={entry} />;
          if (entry.role === "assistant") return <AssistantBubble key={entry.id} entry={entry} />;
          // only the latest error offers a retry (an older question was answered or replaced since)
          return <ErrorBubble key={entry.id} entry={entry} onRetry={entry === last ? onRetry : undefined} disabled={pending} />;
        })}
        {pending ? (
          <li className="chat-row chat-row-assistant">
            <div className="chat-bubble chat-bubble-assistant chat-bubble-pending">
              <span className="spinner-circle" aria-hidden="true" />
              <span>Asistan düşünüyor… 30–60 sn sürebilir.</span>
            </div>
          </li>
        ) : null}
      </ol>
      <div ref={endRef} />
    </div>
  );
}
