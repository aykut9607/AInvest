import { GATEWAY_URL } from "../config";
import { ApiError, request, type ApiResponse, type RequestOptions } from "./http";
import { refresh } from "./identityApi";
import { expireSession, getSession, setSession } from "./session";

const SESSION_EXPIRED = "Your session has expired. Please sign in again.";

// one refresh at a time: Identity rotates the refresh token, so two parallel refreshes with the same
// token would make the second one fail (the token was already used) and sign the user out for nothing
let refreshInFlight: Promise<boolean> | null = null;

// calls the gateway with the user's access token. The access token lives 15 minutes; when the gateway
// answers 401 the refresh token gets a new pair and the call is sent once more with the new token
export async function authorizedRequest<T>(path: string, options: RequestOptions = {}): Promise<ApiResponse<T>> {
  const first = await send<T>(path, options);
  if (first.status !== 401) return first;

  if (!(await refreshTokens())) {
    expireSession();
    throw new ApiError(SESSION_EXPIRED, 401);
  }

  const second = await send<T>(path, options);
  if (second.status === 401) {
    expireSession();
    throw new ApiError(SESSION_EXPIRED, 401);
  }
  return second;
}

function send<T>(path: string, options: RequestOptions): Promise<ApiResponse<T>> {
  const session = getSession();
  if (!session) throw new ApiError(SESSION_EXPIRED, 401);

  return request<T>(`${GATEWAY_URL}${path}`, {
    ...options,
    headers: { ...options.headers, Authorization: `Bearer ${session.accessToken}` },
  });
}

function refreshTokens(): Promise<boolean> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      const session = getSession();
      if (!session) return false;
      try {
        const renewed = await refresh(session.refreshToken);
        setSession({ ...renewed, email: renewed.email || session.email });
        return true;
      } catch {
        return false;
      } finally {
        refreshInFlight = null;
      }
    })();
  }
  return refreshInFlight;
}
