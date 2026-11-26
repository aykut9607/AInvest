import { useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { ROUTES } from "../lib/routes";
import Button from "./Button";

const NAV_ITEMS = [
  { to: ROUTES.dashboard, label: "Panel" },
  { to: ROUTES.profile, label: "Profil" },
  { to: ROUTES.assistant, label: "Asistan" },
  { to: ROUTES.portfolio, label: "Portföy" },
  { to: ROUTES.signals, label: "Piyasa (4.4)" },
] as const;

function NavItems({ onNavigate }: { onNavigate?: () => void }) {
  return (
    <ul>
      {NAV_ITEMS.map((item) => (
        <li key={item.to}>
          <NavLink to={item.to} onClick={onNavigate}>
            {item.label}
          </NavLink>
        </li>
      ))}
    </ul>
  );
}

// shell of every signed-in page: header (brand, navigation, e-mail, Çıkış), main content, footer
export default function Layout() {
  const { session, logout } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [menuOpen, setMenuOpen] = useState(false);
  const [menuPath, setMenuPath] = useState(location.pathname);

  // close the phone menu after navigating (state adjusted during render, no effect needed)
  if (menuPath !== location.pathname) {
    setMenuPath(location.pathname);
    setMenuOpen(false);
  }

  const handleLogout = () => {
    // leave the protected area first, so the guard does not remember this page for the next sign-in
    navigate(ROUTES.login, { replace: true });
    logout();
  };

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">
        İçeriğe geç
      </a>
      <header className="app-header">
        <div className="app-header-inner">
          <Link to={ROUTES.dashboard} className="brand" aria-label="AInvest ana sayfa">
            <span className="brand-mark" aria-hidden="true">
              AI
            </span>
            AInvest
          </Link>
          <nav className="app-nav" aria-label="Ana menü">
            <NavItems />
          </nav>
          <div className="app-user">
            <span className="app-user-email" title={session?.email}>
              {session?.email}
            </span>
            <Button variant="ghost" size="sm" onClick={handleLogout}>
              Çıkış
            </Button>
            <Button
              variant="secondary"
              size="sm"
              className="menu-toggle"
              aria-expanded={menuOpen}
              aria-controls="mobile-menu"
              onClick={() => setMenuOpen((open) => !open)}
            >
              {menuOpen ? "Kapat" : "Menü"}
            </Button>
          </div>
        </div>
        {menuOpen ? (
          <nav id="mobile-menu" className="app-nav-mobile" aria-label="Ana menü (mobil)">
            <NavItems onNavigate={() => setMenuOpen(false)} />
            {session?.email ? <p className="app-nav-mobile-email">{session.email}</p> : null}
          </nav>
        ) : null}
      </header>
      <main id="main" className="app-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
