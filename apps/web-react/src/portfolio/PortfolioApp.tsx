import { useCallback, useEffect, useMemo, useState } from "react";
import { ApiError, createApi, type PortfolioApi, type Session } from "./api";
import AuthPage from "./AuthPage";
import MarketPage from "./MarketPage";
import PanelPage from "./PanelPage";
import PortfolioPage from "./PortfolioPage";
import ProfilePage from "./ProfilePage";
import { problem } from "./text";
import type { IqResult } from "./types";
import { Banner, Button, Loading } from "./ui";
import { useLoad } from "./useLoad";
import "./portfolio.css";

// The pages with their own sign-in (portfolio.html). Inside another app use <PortfolioPage api={...} /> and <MarketPage api={...} /> within a
// <div className="pf"> and import portfolio.css; nothing outside this folder is needed.
const KEY = "ainvest.portfolio.session";
type Page = "profil" | "panel" | "portfoy" | "piyasa";

// the order of the journey: profile -> Financial IQ -> portfolio -> market. Nothing after the profile opens before there
// is a Financial IQ, and the market (4.4) opens only after a portfolio choice was saved
type Step = "none" | "iq" | "chosen";
const PAGES: { id: Page; label: string; needs: Step; why?: string }[] = [
  { id: "profil", label: "Profil", needs: "none" },
  { id: "panel", label: "Finansal IQ", needs: "iq", why: "Önce finansal profilini doldur" },
  { id: "portfoy", label: "Portföy", needs: "iq", why: "Önce finansal profilini doldur" },
  { id: "piyasa", label: "Piyasa (4.4)", needs: "chosen", why: "Önce portföy türünü ve riskini seç" },
];
const RANK: Record<Step, number> = { none: 0, iq: 1, chosen: 2 };

function stored(): Session | null {
  try {
    const text = sessionStorage.getItem(KEY);
    return text ? (JSON.parse(text) as Session) : null;
  } catch {
    return null;
  }
}

function keep(next: Session | null) {
  try {
    if (next) sessionStorage.setItem(KEY, JSON.stringify(next));
    else sessionStorage.removeItem(KEY);
  } catch {
    // private window: the session then lives only until the page is reloaded
  }
}

export default function PortfolioApp() {
  const [session, setSession] = useState<Session | null>(stored);
  const [notice, setNotice] = useState("");
  const userId = session?.userId;
  // the API object lives as long as the same user is signed in; it renews its own tokens
  const api = useMemo(() => {
    const first = stored() ?? session;
    if (!userId || !first) return null;
    return createApi(first, (next) => {
      keep(next);
      if (!next) {
        setNotice("Oturumun süresi doldu. Yeniden giriş yap.");
        setSession(null);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId]);

  return (
    <div className="pf">
      {session && api ? (
        <Shell
          key={session.userId}
          api={api}
          onLogout={() => {
            keep(null);
            setSession(null);
          }}
        />
      ) : (
        <AuthPage
          notice={notice}
          onSession={(next) => {
            keep(next);
            setNotice("");
            setSession(next);
          }}
        />
      )}
    </div>
  );
}

const fromHash = (): Page | null => PAGES.find((p) => `#${p.id}` === window.location.hash)?.id ?? null;

function Shell({ api, onLogout }: { api: PortfolioApi; onLogout: () => void }) {
  const load = useCallback(async () => {
    const missing = (error: unknown) => {
      if (error instanceof ApiError && error.status === 404) return null;
      throw error;
    };
    const user = encodeURIComponent(api.userId);
    const [iq, preferences] = await Promise.all([
      api.get<IqResult>(`/api/financial-iq/${user}/latest`).catch(missing),
      api.get<unknown>(`/api/portfolio/${user}/preferences`).catch(missing),
    ]);
    return { iq, chosen: preferences !== null };
  }, [api]);
  const { data, error, loading, reload } = useLoad(load);
  const iq = data?.iq ?? null;
  const [chosenNow, setChosenNow] = useState(false);
  const reached: Step = !iq ? "none" : data?.chosen || chosenNow ? "chosen" : "iq";
  const [wanted, setWanted] = useState<Page | null>(fromHash);
  // a page is opened only once the steps before it are done; a link or a typed address cannot skip ahead:
  // no score -> profile, a score but no portfolio choice -> the market falls back to the portfolio page
  const allowed = (p: Page) => RANK[PAGES.find((x) => x.id === p)!.needs] <= RANK[reached];
  const page: Page = !iq ? "profil" : wanted && allowed(wanted) ? wanted : wanted === "piyasa" ? "portfoy" : "panel";

  // a refused address is replaced by the page shown, so it cannot open by itself later (e.g. #piyasa typed before the
  // portfolio choice would otherwise jump to the market the moment the choice is saved)
  // (state adjusted while rendering, the React way for "derived from the previous render"; the address follows in an effect)
  if (!loading && wanted && wanted !== page) setWanted(page);
  useEffect(() => {
    if (!loading && window.location.hash && window.location.hash !== `#${page}`) window.history.replaceState(null, "", `#${page}`);
  }, [loading, page]);

  useEffect(() => {
    const changed = () => setWanted(fromHash());
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);

  const go = (to: Page) => {
    setWanted(to);
    window.history.replaceState(null, "", `#${to}`);
    window.scrollTo(0, 0);
  };

  return (
    <>
      <nav className="pf-nav">
        <div>
          <span className="pf-brand">
            <i>AI</i> AInvest
          </span>
          {PAGES.map((p) => {
            const locked = !allowed(p.id);
            return (
              <button key={p.id} type="button" disabled={locked} title={locked ? p.why : undefined} className={page === p.id ? "pf-on" : ""} aria-current={page === p.id ? "page" : undefined} onClick={() => go(p.id)}>
                {p.label}
              </button>
            );
          })}
          <span className="pf-spacer" />
          <span className="pf-email">{api.email}</span>
          <button type="button" onClick={onLogout}>
            Çıkış
          </button>
        </div>
      </nav>
      <main className="pf-main">
        {loading && !iq ? (
          <Loading />
        ) : error !== null && !iq ? (
          <>
            <Banner kind="danger" title="Yüklenemedi">
              {problem(error)}
            </Banner>
            <div>
              <Button kind="quiet" onClick={reload}>
                Yeniden dene
              </Button>
            </div>
          </>
        ) : page === "profil" ? (
          <ProfilePage
            api={api}
            onDone={() => {
              go("panel");
              reload();
            }}
          />
        ) : page === "panel" && iq ? (
          <PanelPage key={iq.resultVersion ?? iq.updatedAt} api={api} iq={iq} onNext={() => go("portfoy")} onEdit={() => go("profil")} />
        ) : page === "portfoy" ? (
          <PortfolioPage api={api} marketOpen={reached === "chosen"} onChosen={() => setChosenNow(true)} onOpenMarket={() => go("piyasa")} onOpenProfile={() => go("profil")} />
        ) : (
          <MarketPage api={api} />
        )}
      </main>
    </>
  );
}
