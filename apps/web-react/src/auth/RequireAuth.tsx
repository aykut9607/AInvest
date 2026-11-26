import { Navigate, Outlet, useLocation } from "react-router-dom";
import { ROUTES, type AuthRedirectState } from "../lib/routes";
import { useAuth } from "./useAuth";

// guards the protected routes: without a session, go to /giris and remember where the user wanted to go
export default function RequireAuth() {
  const { session } = useAuth();
  const location = useLocation();

  if (!session) {
    const state: AuthRedirectState = { from: `${location.pathname}${location.search}` };
    return <Navigate to={ROUTES.login} replace state={state} />;
  }
  return <Outlet />;
}
