import { useCallback, useState } from "react";
import type { SignalAsset, SignalPlan } from "../../types/signals";
import { browserStorage, userKey } from "./safeStorage";
import {
  WATCHLIST_STORAGE_KEY,
  addToWatchlist,
  loadWatchlist,
  removeFromWatchlist,
  saveWatchlist,
  type WatchItem,
} from "./watchlist";

interface State {
  key: string;
  items: WatchItem[];
  // false when the browser blocks localStorage: the list is then lost on reload (the page says so)
  persistent: boolean;
}

function initial(key: string): State {
  const storage = browserStorage("local");
  return { key, items: loadWatchlist(storage, key), persistent: storage !== null };
}

export interface WatchlistApi {
  items: WatchItem[];
  persistent: boolean;
  add: (plan: SignalPlan) => void;
  remove: (asset: SignalAsset) => void;
}

export function useWatchlist(userId: string | null | undefined): WatchlistApi {
  const key = userKey(WATCHLIST_STORAGE_KEY, userId);
  const [state, setState] = useState<State>(() => initial(key));

  // another user signed in on this tab: load their list (state adjusted during render, no effect needed)
  if (state.key !== key) setState(initial(key));

  const commit = useCallback(
    (items: WatchItem[]) => {
      const persistent = saveWatchlist(browserStorage("local"), key, items);
      setState({ key, items, persistent });
    },
    [key]
  );

  const add = useCallback((plan: SignalPlan) => commit(addToWatchlist(state.items, plan)), [commit, state.items]);
  const remove = useCallback((asset: SignalAsset) => commit(removeFromWatchlist(state.items, asset)), [commit, state.items]);

  return { items: state.items, persistent: state.persistent, add, remove };
}
