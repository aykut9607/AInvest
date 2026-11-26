import { useEffect, useId, useReducer, useRef, useState } from "react";
import { askAssistant } from "../api/aiApi";
import { RateLimitError, isAbortError } from "../api/http";
import { useAuth } from "../auth/useAuth";
import Button from "../components/Button";
import Card from "../components/Card";
import Notice from "../components/Notice";
import PageHeader from "../components/PageHeader";
import RateLimitNotice from "../components/RateLimitNotice";
import Composer from "../components/assistant/Composer";
import TranscriptView from "../components/assistant/TranscriptView";
import { SUGGESTED_QUESTIONS } from "../components/assistant/assistantLabels";
import {
  TRANSCRIPT_STORAGE_KEY,
  loadTranscript,
  nextEntryId,
  normalizeQuestion,
  saveTranscript,
  transcriptReducer,
  type StoredTranscript,
} from "../components/assistant/transcript";
import { browserStorage, userKey } from "../components/signals/safeStorage";
import { errorMessage } from "../lib/errors";
import type { AssistantMode } from "../types/api";
import "../components/assistant/assistant.css";

function Conversation({ storageKey, restored }: { storageKey: string; restored: StoredTranscript }) {
  const [state, dispatch] = useReducer(transcriptReducer, { entries: restored.entries, pendingId: null });
  const [mode, setMode] = useState<AssistantMode>(restored.mode);
  const [draft, setDraft] = useState("");
  const [rateLimit, setRateLimit] = useState<RateLimitError | null>(null);
  const controller = useRef<AbortController | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const wasPending = useRef(false);
  const suggestionsId = useId();
  const pending = state.pendingId !== null;
  const blocked = pending || rateLimit !== null;

  useEffect(() => {
    saveTranscript(browserStorage("session"), storageKey, { entries: state.entries, mode });
  }, [storageKey, state.entries, mode]);

  // leaving the page cancels a question that is still waiting
  useEffect(() => () => controller.current?.abort(), []);

  // the input was disabled while waiting: give it the focus back once the answer is there
  useEffect(() => {
    if (wasPending.current && !pending) textareaRef.current?.focus();
    wasPending.current = pending;
  }, [pending]);

  // set synchronously, so a second click before the next render cannot send a second request
  const inFlight = useRef(false);

  const ask = async (text: string) => {
    const question = normalizeQuestion(text);
    if (inFlight.current || rateLimit !== null || question === null) return;
    inFlight.current = true;
    const id = nextEntryId();
    dispatch({ type: "ask", id, question, at: new Date().toISOString() });
    setDraft("");
    const current = new AbortController();
    controller.current = current;
    try {
      const response = await askAssistant(question, mode, { signal: current.signal });
      if (!current.signal.aborted) dispatch({ type: "answer", id, response, at: new Date().toISOString() });
    } catch (err) {
      if (current.signal.aborted || isAbortError(err)) return;
      if (err instanceof RateLimitError) {
        // the gateway allows 10 AI requests a minute per user: the question goes back into the input
        dispatch({ type: "withdraw", id });
        setDraft(question);
        setRateLimit(err);
        return;
      }
      dispatch({ type: "fail", id, message: errorMessage(err, "Asistan cevap veremedi."), at: new Date().toISOString() });
    } finally {
      if (controller.current === current) inFlight.current = false;
    }
  };

  const clear = () => {
    controller.current?.abort();
    controller.current = null;
    inFlight.current = false;
    dispatch({ type: "clear" });
  };

  const empty = state.entries.length === 0 && !pending;

  return (
    <Card
      className="assistant-card"
      title="Konuşma"
      actions={
        state.entries.length > 0 ? (
          <Button variant="ghost" size="sm" onClick={clear}>
            Konuşmayı temizle
          </Button>
        ) : null
      }
    >
      <div className="stack">
        {empty ? (
          <div className="assistant-empty">
            <p className="assistant-empty-title">Merhaba! Finansal durumunla ilgili bir soru sor.</p>
            <p className="text-sm text-secondary">Aşağıdaki örneklerden birine dokunabilir ya da kendi sorunu yazabilirsin.</p>
          </div>
        ) : (
          <TranscriptView entries={state.entries} pending={pending} onRetry={(question) => void ask(question)} />
        )}

        <div className="suggestions">
          <p className="field-label" id={suggestionsId}>
            Örnek sorular
          </p>
          <ul className={`suggestion-list${empty ? "" : " is-compact"}`} aria-labelledby={suggestionsId}>
            {SUGGESTED_QUESTIONS.map((question) => (
              <li key={question}>
                <button type="button" className="suggestion-chip" disabled={blocked} onClick={() => void ask(question)}>
                  {question}
                </button>
              </li>
            ))}
          </ul>
        </div>

        {rateLimit ? (
          <RateLimitNotice
            key={rateLimit.retryAt}
            seconds={rateLimit.retryAfterSeconds}
            message={(s) => `Dakikada en fazla 10 soru sorulabilir. ${s} saniye sonra tekrar gönderebilirsin; sorun kutuda duruyor.`}
            onDone={() => setRateLimit(null)}
          />
        ) : null}

        <Composer
          value={draft}
          onChange={setDraft}
          onSend={(question) => void ask(question)}
          disabled={blocked}
          busy={pending}
          textareaRef={textareaRef}
        />

        <div className="mode-toggle">
          <label className="mode-toggle-label">
            <input
              type="checkbox"
              role="switch"
              checked={mode === "tools"}
              disabled={pending}
              onChange={(event) => setMode(event.target.checked ? "tools" : "router")}
            />
            <span>Gelişmiş: araç çağırma modu (tools)</span>
          </label>
          <p className="field-hint">
            {mode === "tools"
              ? "Model hangi veriyi okuyacağına kendisi karar verir. Ollama'da llama3.1:8b modeli gerekir; yoksa cevap kodun hazırladığı şablona düşer."
              : "Varsayılan mod (router): hangi verinin okunacağını kod seçer, model yalnızca cümleye çevirir."}
          </p>
        </div>
      </div>
    </Card>
  );
}

// Assistant: questions answered from the user's own data (POST /ai/assistant/ask through the gateway).
export default function AssistantPage() {
  const { session } = useAuth();
  const storageKey = userKey(TRANSCRIPT_STORAGE_KEY, session?.userId);
  // read once per user; Conversation is keyed by the storage key, so another user starts with their own transcript
  const [restored, setRestored] = useState(() => ({ key: storageKey, value: loadTranscript(browserStorage("session"), storageKey) }));
  if (restored.key !== storageKey) setRestored({ key: storageKey, value: loadTranscript(browserStorage("session"), storageKey) });

  return (
    <div className="page page-narrow">
      <PageHeader title="Asistan" description="Finansal durumunla ilgili sorularını kendi verilerinle cevaplayan asistan." />
      <Notice title="Asistan neyi görür?">
        <div className="stack-sm">
          <p>
          Asistan, ağ geçidi üzerinden oturumunla yalnızca senin profilini, Finansal IQ sonucunu, skor geçmişini, uyarılarını
          ve portföy önerini okur. Piyasa fiyatlarını (kripto, hisse, döviz, altın) henüz göremez.
          </p>
          <p>
          Sayıları kod hesaplar, model yalnızca cümleye çevirir. Her soru ayrı cevaplanır; asistan önceki mesajları
          hatırlamaz. Yerel model bir cevap için 30–60 saniye düşünebilir.
          </p>
        </div>
      </Notice>
      <Conversation key={restored.key} storageKey={restored.key} restored={restored.value} />
    </div>
  );
}
