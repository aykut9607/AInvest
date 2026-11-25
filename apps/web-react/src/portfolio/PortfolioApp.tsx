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

// the order of the journey: nothing after the profile opens before there is a Financial IQ
const PAGES: { id: Page; label: string; needsIq: boolean }[] = [
  { id: "profil", label: "Profil", needsIq: false },
  { id: "panel", label: "Finansal IQ", needsIq: true },
  { id: "portfoy", label: "Portföy", needsIq: true },
  { id: "piyasa", label: "Piyasa (4.4)", needsIq: true },
];

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
  const load = useCallback(
    () =>
      api.get<IqResult>(`/api/financial-iq/${encodeURIComponent(api.userId)}/latest`).catch((error: unknown) => {
        if (error instanceof ApiError && error.status === 404) return null;
        throw error;
      }),
    [api],
  );
  const { data: iq, error, loading, reload } = useLoad(load);
  const [wanted, setWanted] = useState<Page | null>(fromHash);
  // without a score every road leads to the profile; with one the score is the first stop
  const page: Page = !iq ? "profil" : (wanted ?? "panel");

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
            const locked = p.needsIq && !iq;
            return (
              <button key={p.id} type="button" disabled={locked} title={locked ? "Önce finansal profilini doldur" : undefined} className={page === p.id ? "pf-on" : ""} aria-current={page === p.id ? "page" : undefined} onClick={() => go(p.id)}>
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
          <PortfolioPage api={api} onOpenMarket={() => go("piyasa")} onOpenProfile={() => go("profil")} />
        ) : (
          <MarketPage api={api} />
        )}
      </main>
    </>
  );
}
