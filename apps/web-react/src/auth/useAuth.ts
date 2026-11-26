import { createContext, useContext } from "react";
import type { AuthSession } from "../types/api";

export interface AuthContextValue {
  // null when signed out; userId (JWT sub) and email for the UI
  session: AuthSession | null;
  // message for the sign-in page, e.g. after the session expired; null otherwise
  notice: string | null;
  clearNotice: () => void;
  // both sign the user in (session stored in sessionStorage) and resolve with the new session
  login: (email: string, password: string) => Promise<AuthSession>;
  register: (email: string, password: string) => Promise<AuthSession>;
  // forgets the tokens (Identity has no logout endpoint; the refresh token simply expires)
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth must be used inside <AuthProvider>");
  return value;
}

export const SESSION_EXPIRED_NOTICE = "Oturumunuzun süresi doldu. Lütfen yeniden giriş yapın.";
