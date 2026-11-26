import { describe, expect, it } from "vitest";
import { MemoryStorage } from "../../test/helpers";
import type { AskResponse } from "../../types/api";
import { answerNote, intentLabel } from "./assistantLabels";
import {
  EMPTY_TRANSCRIPT,
  MAX_ENTRIES,
  loadTranscript,
  normalizeQuestion,
  parseStoredTranscript,
  saveTranscript,
  transcriptReducer,
  type TranscriptState,
} from "./transcript";

const AT = "2026-11-24T10:00:00.000Z";

function answer(overrides: Partial<AskResponse> = {}): AskResponse {
  return {
    answer: "Toplam borcun 90.000 TL.",
    persona: "assistant",
    mode: "router",
    intents: ["DEBT"],
    disclaimer: "Bu bilgi yalnızca eğitim amaçlıdır, yatırım tavsiyesi değildir.",
    model: "gemma3:4b",
    numbersVerified: true,
    fallbackUsed: false,
    fallbackReason: null,
    ...overrides,
  };
}

function asked(question = "Kaç para borcum var?", id = "q1", state: TranscriptState = EMPTY_TRANSCRIPT) {
  return transcriptReducer(state, { type: "ask", id, question, at: AT });
}

describe("transcript reducer", () => {
  it("adds the question, waits for one answer at a time, then adds the answer", () => {
    let state = asked("  Kaç para borcum var?  ");
    expect(state.pendingId).toBe("q1");
    expect(state.entries).toEqual([{ id: "q1", role: "user", text: "Kaç para borcum var?", at: AT }]);

    // a second question while waiting is ignored
    expect(asked("Başka soru", "q2", state)).toBe(state);

    // an answer for another id (an old, cancelled call) changes nothing
    expect(transcriptReducer(state, { type: "answer", id: "zz", response: answer(), at: AT })).toBe(state);

    state = transcriptReducer(state, { type: "answer", id: "q1", response: answer(), at: AT });
    expect(state.pendingId).toBeNull();
    expect(state.entries[1]).toMatchObject({ id: "q1:a", role: "assistant", replyTo: "q1" });
  });

  it("ignores empty and too long questions", () => {
    expect(asked("   ")).toBe(EMPTY_TRANSCRIPT);
    expect(asked("x".repeat(501))).toBe(EMPTY_TRANSCRIPT);
    expect(normalizeQuestion("x".repeat(500))).toHaveLength(500);
  });

  it("records a failure with the question so it can be asked again", () => {
    const state = transcriptReducer(asked(), { type: "fail", id: "q1", message: "İstek zaman aşımına uğradı.", at: AT });
    expect(state.pendingId).toBeNull();
    expect(state.entries[1]).toEqual({
      id: "q1:e",
      role: "error",
      replyTo: "q1",
      question: "Kaç para borcum var?",
      message: "İstek zaman aşımına uğradı.",
      at: AT,
    });
  });

  it("withdraws a rate-limited question and clears everything", () => {
    const state = transcriptReducer(asked(), { type: "withdraw", id: "q1" });
    expect(state).toEqual(EMPTY_TRANSCRIPT);
    const answered = transcriptReducer(asked(), { type: "answer", id: "q1", response: answer(), at: AT });
    expect(transcriptReducer(answered, { type: "clear" })).toEqual(EMPTY_TRANSCRIPT);
  });

  it("keeps at most MAX_ENTRIES entries", () => {
    let state = EMPTY_TRANSCRIPT;
    for (let i = 0; i < MAX_ENTRIES; i += 1) {
      state = asked(`Soru ${i}`, `q${i}`, state);
      state = transcriptReducer(state, { type: "answer", id: `q${i}`, response: answer(), at: AT });
    }
    expect(state.entries).toHaveLength(MAX_ENTRIES);
    expect(state.entries[0]).toMatchObject({ role: "user", text: `Soru ${MAX_ENTRIES / 2}` });
  });
});

describe("transcript storage", () => {
  it("round-trips answered entries and the mode", () => {
    const storage = new MemoryStorage();
    const state = transcriptReducer(asked(), { type: "answer", id: "q1", response: answer({ mode: "tools" }), at: AT });
    expect(saveTranscript(storage, "t", { entries: state.entries, mode: "tools" })).toBe(true);
    expect(loadTranscript(storage, "t")).toEqual({ entries: state.entries, mode: "tools" });
  });

  it("drops a question that never got an answer and anything malformed", () => {
    const stored = parseStoredTranscript({
      mode: "weird",
      entries: [
        { id: "q1", role: "user", text: "Cevapsız soru", at: AT },
        { id: "q2", role: "user", text: "Cevaplı", at: AT },
        { id: "q2:a", role: "assistant", replyTo: "q2", at: AT, response: { answer: "Tamam", intents: ["FAQ", 3] } },
        { id: "x", role: "assistant", replyTo: "q2", at: AT, response: { answer: 42 } },
        { id: "y", role: "system", at: AT },
      ],
    });
    expect(stored.mode).toBe("router");
    expect(stored.entries.map((e) => e.id)).toEqual(["q2", "q2:a"]);
    const reply = stored.entries[1];
    expect(reply.role === "assistant" && reply.response).toMatchObject({ answer: "Tamam", intents: ["FAQ"], model: null, numbersVerified: false });
  });

  it("works without storage and with storage that throws", () => {
    class Throwing extends MemoryStorage {
      override getItem(): string | null {
        throw new Error("blocked");
      }
      override setItem(): void {
        throw new Error("blocked");
      }
    }
    expect(loadTranscript(null, "t")).toEqual({ entries: [], mode: "router" });
    expect(loadTranscript(new Throwing(), "t")).toEqual({ entries: [], mode: "router" });
    expect(saveTranscript(new Throwing(), "t", { entries: [], mode: "tools" })).toBe(false);
  });
});

describe("assistant labels", () => {
  it("translates intents, keeps unknown ones and explains the template answers", () => {
    expect(intentLabel("DEBT")).toBe("Borç");
    expect(intentLabel("get_new_tool")).toBe("get_new_tool");
    expect(answerNote(answer({ fallbackUsed: true, fallbackReason: "BLOCKED_INPUT", intents: [] }))?.text).toContain("güvenlik filtresine");
    expect(answerNote(answer({ fallbackUsed: true, fallbackReason: "DATA_UNAVAILABLE", intents: [] }))?.tone).toBe("warning");
    expect(answerNote(answer({ intents: ["MARKET_PRICE"] }))?.text).toContain("piyasa fiyatlarını");
    expect(answerNote(answer())).toBeNull();
  });
});
