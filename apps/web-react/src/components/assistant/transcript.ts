// The assistant conversation as shown on screen. The API is single-turn (every question is answered on its own, the
// assistant does not remember earlier messages); the transcript is only the page's memory. Kept in this tab's
// sessionStorage per user, so a reload does not lose it; in memory only when storage is blocked.
import { ASSISTANT_QUESTION_MAX_LENGTH } from "../../api/aiApi";
import type { AskResponse, AssistantMode, FallbackReason } from "../../types/api";
import { readJson, removeKey, writeJson } from "../signals/safeStorage";

export const TRANSCRIPT_STORAGE_KEY = "ainvest.assistant.transcript.v1";
// oldest entries are dropped beyond this (keeps sessionStorage small)
export const MAX_ENTRIES = 60;

export interface UserEntry {
  id: string;
  role: "user";
  text: string;
  at: string;
}

export interface AssistantEntry {
  id: string;
  role: "assistant";
  replyTo: string;
  response: AskResponse;
  at: string;
}

// the call failed (network, timeout, server error); the question can be sent again
export interface ErrorEntry {
  id: string;
  role: "error";
  replyTo: string;
  question: string;
  message: string;
  at: string;
}

export type TranscriptEntry = UserEntry | AssistantEntry | ErrorEntry;

export interface TranscriptState {
  entries: TranscriptEntry[];
  // id of the question waiting for an answer; one question at a time
  pendingId: string | null;
}

export type TranscriptAction =
  | { type: "ask"; id: string; question: string; at: string }
  | { type: "answer"; id: string; response: AskResponse; at: string }
  | { type: "fail"; id: string; message: string; at: string }
  // the gateway refused the question (429): it disappears from the transcript and goes back to the input
  | { type: "withdraw"; id: string }
  | { type: "clear" };

export const EMPTY_TRANSCRIPT: TranscriptState = { entries: [], pendingId: null };

// what the input may send: trimmed, 1..500 characters (the AI service answers 422 otherwise)
export function normalizeQuestion(text: string): string | null {
  const question = text.trim();
  if (question.length === 0 || question.length > ASSISTANT_QUESTION_MAX_LENGTH) return null;
  return question;
}

function cap(entries: TranscriptEntry[]): TranscriptEntry[] {
  return entries.length > MAX_ENTRIES ? entries.slice(entries.length - MAX_ENTRIES) : entries;
}

export function transcriptReducer(state: TranscriptState, action: TranscriptAction): TranscriptState {
  switch (action.type) {
    case "ask": {
      const question = normalizeQuestion(action.question);
      if (state.pendingId !== null || question === null) return state;
      const entry: UserEntry = { id: action.id, role: "user", text: question, at: action.at };
      return { entries: cap([...state.entries, entry]), pendingId: action.id };
    }
    case "answer": {
      if (state.pendingId !== action.id) return state;
      const entry: AssistantEntry = { id: `${action.id}:a`, role: "assistant", replyTo: action.id, response: action.response, at: action.at };
      return { entries: cap([...state.entries, entry]), pendingId: null };
    }
    case "fail": {
      if (state.pendingId !== action.id) return state;
      const question = state.entries.find((e): e is UserEntry => e.role === "user" && e.id === action.id)?.text ?? "";
      const entry: ErrorEntry = {
        id: `${action.id}:e`,
        role: "error",
        replyTo: action.id,
        question,
        message: action.message,
        at: action.at,
      };
      return { entries: cap([...state.entries, entry]), pendingId: null };
    }
    case "withdraw": {
      if (state.pendingId !== action.id) return state;
      return { entries: state.entries.filter((e) => e.id !== action.id), pendingId: null };
    }
    case "clear":
      return EMPTY_TRANSCRIPT;
    default:
      return state;
  }
}

// ---- persistence -----------------------------------------------------------------------------------------------

const MODES: AssistantMode[] = ["router", "tools"];

function isText(value: unknown): value is string {
  return typeof value === "string";
}

function parseResponse(value: unknown): AskResponse | null {
  if (!value || typeof value !== "object") return null;
  const r = value as Record<string, unknown>;
  if (!isText(r.answer)) return null;
  return {
    answer: r.answer,
    persona: "assistant",
    mode: MODES.includes(r.mode as AssistantMode) ? (r.mode as AssistantMode) : "router",
    intents: Array.isArray(r.intents) ? r.intents.filter(isText) : [],
    disclaimer: isText(r.disclaimer) ? r.disclaimer : "",
    model: isText(r.model) ? r.model : null,
    numbersVerified: r.numbersVerified === true,
    fallbackUsed: r.fallbackUsed === true,
    fallbackReason: isText(r.fallbackReason) ? (r.fallbackReason as FallbackReason) : null,
  };
}

function parseEntry(value: unknown): TranscriptEntry | null {
  if (!value || typeof value !== "object") return null;
  const e = value as Record<string, unknown>;
  if (!isText(e.id) || !isText(e.at)) return null;
  if (e.role === "user" && isText(e.text)) return { id: e.id, role: "user", text: e.text, at: e.at };
  if (e.role === "assistant" && isText(e.replyTo)) {
    const response = parseResponse(e.response);
    return response ? { id: e.id, role: "assistant", replyTo: e.replyTo, response, at: e.at } : null;
  }
  if (e.role === "error" && isText(e.replyTo) && isText(e.question) && isText(e.message)) {
    return { id: e.id, role: "error", replyTo: e.replyTo, question: e.question, message: e.message, at: e.at };
  }
  return null;
}

export interface StoredTranscript {
  entries: TranscriptEntry[];
  mode: AssistantMode;
}

// a question that was still waiting when the page was left has no answer: it is dropped with the rest of the
// unreadable entries
export function parseStoredTranscript(value: unknown): StoredTranscript {
  const empty: StoredTranscript = { entries: [], mode: "router" };
  if (!value || typeof value !== "object") return empty;
  const v = value as Record<string, unknown>;
  const parsed = Array.isArray(v.entries) ? v.entries.map(parseEntry).filter((e): e is TranscriptEntry => e !== null) : [];
  const answered = new Set(parsed.filter((e) => e.role !== "user").map((e) => (e as AssistantEntry | ErrorEntry).replyTo));
  const entries = parsed.filter((e) => e.role !== "user" || answered.has(e.id));
  return { entries: cap(entries), mode: MODES.includes(v.mode as AssistantMode) ? (v.mode as AssistantMode) : "router" };
}

export function loadTranscript(storage: Storage | null, key: string): StoredTranscript {
  return parseStoredTranscript(readJson(storage, key));
}

export function saveTranscript(storage: Storage | null, key: string, transcript: StoredTranscript): boolean {
  if (transcript.entries.length === 0 && transcript.mode === "router") return removeKey(storage, key);
  return writeJson(storage, key, transcript);
}

let sequence = 0;
// unique enough for React keys and reducer ids within a tab
export function nextEntryId(now: number = Date.now()): string {
  sequence += 1;
  return `${now.toString(36)}-${sequence}`;
}
