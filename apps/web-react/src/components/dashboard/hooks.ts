import { useCallback, useEffect, useRef, useState } from "react";
import { RateLimitError, isAbortError } from "../../api/http";

export interface OnDemandState<T> {
  // last successful result (kept while a new run is on the way)
  data: T | undefined;
  error: unknown;
  loading: boolean;
  // runs the call; a run still on the way is cancelled first
  start: () => void;
}

// An API call that runs only when the user asks (the AI explanations: rate limited and slow, never automatic).
// Cancelled when the component unmounts.
export function useOnDemand<T>(run: (signal: AbortSignal) => Promise<T>): OnDemandState<T> {
  const [state, setState] = useState<{ data: T | undefined; error: unknown; loading: boolean }>({
    data: undefined,
    error: null,
    loading: false,
  });
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const start = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    setState((previous) => ({ data: previous.data, error: null, loading: true }));
    run(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false });
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbortError(error)) return;
        setState((previous) => ({ data: previous.data, error, loading: false }));
      }
    );
  }, [run]);

  return { ...state, start };
}

// While a 429 countdown runs the button that would send the same request again stays disabled.
// blocked = the error is a RateLimitError whose countdown has not finished; pass onDone to ErrorBox.onRateLimitDone.
export function useRateLimitGate(error: unknown): { blocked: boolean; onDone: () => void } {
  const [clearedAt, setClearedAt] = useState<number | null>(null);
  const retryAt = error instanceof RateLimitError ? error.retryAt : null;
  const onDone = useCallback(() => {
    if (retryAt !== null) setClearedAt(retryAt);
  }, [retryAt]);
  return { blocked: retryAt !== null && clearedAt !== retryAt, onDone };
}

// Width of an element in CSS pixels, kept up to date with a ResizeObserver (charts draw in real pixels so text keeps
// its size on a phone). `fallback` is used before the first measurement and on the server.
export function useElementWidth<T extends HTMLElement>(fallback: number): [(node: T | null) => (() => void) | undefined, number] {
  const [width, setWidth] = useState(fallback);
  const ref = useCallback((node: T | null) => {
    if (!node || typeof ResizeObserver === "undefined") return undefined;
    const observer = new ResizeObserver((entries) => {
      const next = Math.floor(entries[0]?.contentRect.width ?? 0);
      if (next > 0) setWidth(next);
    });
    observer.observe(node);
    return () => observer.disconnect();
  }, []);
  return [ref, width];
}
