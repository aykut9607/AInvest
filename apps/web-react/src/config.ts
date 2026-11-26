// The web app talks to the Edge Gateway only: it checks the token and forwards each path to its service
// (/auth -> Identity, /api/Profiles -> Finance Profile, /api/financial-iq -> Financial IQ, /ai -> AI/RAG).
// The services' own ports (5293, 5109, 8001) are never used from the browser.
const env = import.meta.env ?? {};

function trimTrailingSlash(url: string): string {
  return url.replace(/\/+$/, "");
}

export const GATEWAY_URL = trimTrailingSlash(env.VITE_GATEWAY_URL?.trim() || "http://localhost:5000");

// "mock" until the Portfolio Service exists (the gateway on main has no /api/portfolio route yet)
export type PortfolioSource = "mock" | "service";
export const PORTFOLIO_SOURCE: PortfolioSource = env.VITE_PORTFOLIO_SOURCE?.trim() === "service" ? "service" : "mock";

export const REQUEST_TIMEOUT_MS = 10_000;
// the AI service waits up to 60 s for the local model; give it 10 s more before giving up on our side
export const AI_REQUEST_TIMEOUT_MS = 70_000;
