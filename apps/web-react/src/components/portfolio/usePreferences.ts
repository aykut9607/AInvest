import { useCallback, useState } from "react";
import { browserStorage, userKey } from "../signals/safeStorage";
import { PREFERENCES_STORAGE_KEY, loadPreferences, savePreferences, type PortfolioPreferences } from "./preferences";

interface State {
  key: string;
  preferences: PortfolioPreferences;
}

// the user's choices for this tab (sessionStorage, per user); in memory only when storage is blocked
export function usePreferences(userId: string | null | undefined) {
  const key = userKey(PREFERENCES_STORAGE_KEY, userId);
  const [state, setState] = useState<State>(() => ({ key, preferences: loadPreferences(browserStorage("session"), key) }));

  // another user signed in on this tab (state adjusted during render, no effect needed)
  if (state.key !== key) setState({ key, preferences: loadPreferences(browserStorage("session"), key) });

  const update = useCallback(
    (patch: Partial<PortfolioPreferences>) => {
      const preferences = { ...state.preferences, ...patch };
      savePreferences(browserStorage("session"), key, preferences);
      setState({ key, preferences });
    },
    [key, state.preferences]
  );

  return { preferences: state.preferences, update };
}
