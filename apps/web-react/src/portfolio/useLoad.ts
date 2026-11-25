import { useCallback, useEffect, useState } from "react";

interface State<T> {
  data: T | null;
  error: unknown;
  loading: boolean;
}

// loads when `load` changes (wrap it in useCallback) and on reload(); the old data stays visible while a reload runs
export function useLoad<T>(load: () => Promise<T>): State<T> & { reload: () => void; set: (data: T) => void } {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: true });
  const [run, setRun] = useState(0);

  useEffect(() => {
    let live = true;
    load().then(
      (data) => live && setState({ data, error: null, loading: false }),
      (error: unknown) => live && setState((old) => ({ data: old.data, error, loading: false })),
    );
    return () => {
      live = false;
    };
  }, [load, run]);

  const reload = useCallback(() => {
    setState((old) => ({ ...old, loading: true }));
    setRun((n) => n + 1);
  }, []);
  const set = useCallback((data: T) => setState({ data, error: null, loading: false }), []);
  return { ...state, reload, set };
}
