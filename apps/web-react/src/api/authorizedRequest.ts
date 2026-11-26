import { GATEWAY_URL } from "../config";
import { ApiError, RateLimitError, SessionExpiredError, request, throwIfRateLimited, type ApiResponse, type RequestOptions } from "./http";
import { refresh } from "./identityApi";
import { expireSession, getSession, setSession } from "./session";

// One refresh at a time: Identity rotates the refresh token, so two parallel refreshes with the same token would
// make the second one fail (already used) and sign the user out for nothing.
let refreshInFlight: Promise<boolean> | null = null;

// Calls the gateway with the user's access token (never an X-User-Id header: the gateway writes it from the token).
// The access token lives 15 minutes; on 401 the refresh token buys a new pair and the call is sent exactly once
// more. A second 401 (or a refused refresh) ends the session. 429 throws RateLimitError.
export async function authorizedRequest<T>(path: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
  const first = await send<T>(path, options);
  throwIfRateLimited(first.response);
  if (first.response.status !== 401) return first.response;

  // another call may have refreshed while this one was on the way: then just retry with the newer token
  const alreadyRefreshed = getSession()?.accessToken !== first.token;
  if (!alreadyRefreshed && !(await refreshTokens())) {
    expireSession();
    throw new SessionExpiredError();
  }

  const second = await send<T>(path, options);
  throwIfRateLimited(second.response);
  if (second.response.status === 401) {
    expireSession();
    throw new SessionExpiredError();
  }
  return second.response;
}

// the signed-in user's id (JWT "sub"); the gateway answers 403 for any other id in the URL
export function currentUserId(): string {
  const session = getSession();
  if (!session) throw new SessionExpiredError();
  return session.userId;
}

async function send<T>(path: string, options: RequestOptions): Promise<{ response: ApiResponse<T>; token: string }> {
  const session = getSession();
  if (!session) throw new SessionExpiredError();
  const token = session.accessToken;
  const response = await request<T>(`${GATEWAY_URL}${path}`, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${token}` },
  });
  return { response, token };
}

function refreshTokens(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const session = getSession();
      if (!session) return false;
      try {
        const renewed = await refresh(session.refreshToken, session.email);
        // the user may have signed out while the refresh was on the way
        if (getSession()?.refreshToken !== session.refreshToken) return getSession() !== null;
        setSession(renewed);
        return true;
      } catch (err) {
        // Identity refused the token (401, or 400 for a malformed one): the session is over. A network error or a
        // 5xx says nothing about the token, so it is passed on and the user stays signed in.
        if (err instanceof ApiError && !(err instanceof RateLimitError) && err.status !== undefined && err.status < 500) {
          return false;
        }
        throw err;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}
