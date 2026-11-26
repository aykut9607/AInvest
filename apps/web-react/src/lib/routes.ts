import type { IqCalculation } from "../types/api";

// every route path in one place (Turkish URLs); link with ROUTES.x, never a string literal
export const ROUTES = {
  home: "/",
  login: "/giris",
  register: "/kayit",
  profile: "/profil",
  dashboard: "/panel",
  assistant: "/asistan",
  portfolio: "/portfoy",
  signals: "/piyasa",
} as const;

export type RoutePath = (typeof ROUTES)[keyof typeof ROUTES];

// what LoginPage / RequireAuth pass along in location.state
export interface AuthRedirectState {
  // where the user wanted to go before being sent to /giris
  from?: string;
}

// what ProfilePage passes to /panel after "Kaydet ve hesapla": the fresh result, so the dashboard can show it
// before (or instead of) fetching /latest
export interface DashboardLocationState {
  calculation?: IqCalculation;
}
