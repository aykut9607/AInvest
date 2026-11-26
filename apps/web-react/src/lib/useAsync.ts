import { useCallback, useEffect, useState } from "react";
import { isAbortError } from "../api/http";

export interface AsyncState<T> {
  // last successful result (kept while reloading); undefined before the first one
  data: T | undefined;
  // what the last attempt threw (ApiError, RateLimitError, ...); null when it succeeded
  error: unknown;
  loading: boolean;
  // runs the loader again (e.g. a "Tekrar dene" button)
  reload: () => void;
}

interface State<T> {
  data: T | undefined;
  error: unknown;
  loading: boolean;
  loader: unknown;
}

// Runs an API call when the component mounts and whenever `load` changes; cancels it on unmount.
// Memoise the loader so it does not run on every render:
//   const profile = useAsync(useCallback((signal) => getProfile({ signal }), []));
export function useAsync<T>(load: (signal: AbortSignal) => Promise<T>): AsyncState<T> {
  const [attempt, setAttempt] = useState(0);
  const [state, setState] = useState<State<T>>({ data: undefined, error: null, loading: true, loader: load });

  // a new loader (its dependencies changed): show the loading state right away, without an extra effect pass
  if (state.loader !== load) {
    setState({ data: state.data, error: null, loading: true, loader: load });
  }

  useEffect(() => {
    const controller = new AbortController();
    load(controller.signal).then(
      (data) => {
        if (!controller.signal.aborted) setState({ data, error: null, loading: false, loader: load });
      },
      (error: unknown) => {
        if (controller.signal.aborted || isAbortError(error)) return;
        setState((previous) => ({ data: previous.data, error, loading: false, loader: load }));
      }
    );
    return () => controller.abort();
  }, [load, attempt]);

  const reload = useCallback(() => {
    setState((previous) => ({ ...previous, error: null, loading: true }));
    setAttempt((n) => n + 1);
  }, []);

  return { data: state.data, error: state.error, loading: state.loading, reload };
}
