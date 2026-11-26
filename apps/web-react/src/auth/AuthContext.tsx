import { useCallback, useEffect, useMemo, useState, useSyncExternalStore, type ReactNode } from "react";
import * as identityApi from "../api/identityApi";
import { clearSession, getSession, onSessionExpired, setSession, subscribeSession } from "../api/session";
import { AuthContext, SESSION_EXPIRED_NOTICE, type AuthContextValue } from "./useAuth";

// Session state for React. The tokens themselves live in api/session.ts (the API layer refreshes them in place);
// this provider re-renders on every change and turns an expired session into a notice for /giris.
// RequireAuth then sends the user to the sign-in page.
export function AuthProvider({ children }: { children: ReactNode }) {
  const session = useSyncExternalStore(subscribeSession, getSession, getSession);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => onSessionExpired(() => setNotice(SESSION_EXPIRED_NOTICE)), []);

  const login = useCallback(async (email: string, password: string) => {
    const next = await identityApi.login(email, password);
    setSession(next);
    setNotice(null);
    return next;
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const next = await identityApi.register(email, password);
    setSession(next);
    setNotice(null);
    return next;
  }, []);

  const logout = useCallback(() => {
    setNotice(null);
    clearSession();
  }, []);

  const clearNotice = useCallback(() => setNotice(null), []);

  const value = useMemo<AuthContextValue>(
    () => ({ session, notice, clearNotice, login, register, logout }),
    [session, notice, clearNotice, login, register, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
