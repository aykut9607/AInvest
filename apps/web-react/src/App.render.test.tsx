import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, it } from "vitest";
import { AppRoutes } from "./App";
import { clearSession, setSession } from "./api/session";
import { AuthProvider } from "./auth/AuthContext";
import { makeJwt } from "./test/helpers";

// Smoke test without a browser or a server: every route renders (effects do not run on the server, so no fetch).
function render(path: string): string {
  return renderToString(
    <MemoryRouter initialEntries={[path]}>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </MemoryRouter>
  );
}

function signIn() {
  setSession({
    accessToken: makeJwt({ sub: "u-1", email: "demo.medium@ainvest.local" }),
    refreshToken: "r",
    userId: "u-1",
    email: "demo.medium@ainvest.local",
  });
}

afterEach(() => clearSession());

describe("routes", () => {
  it("renders the public sign-in and register pages", () => {
    const login = render("/giris");
    expect(login).toContain("Giriş yap");
    expect(login).toContain("E-posta");
    expect(login).toContain("Kayıt ol");

    const register = render("/kayit");
    expect(register).toContain("Hesap oluştur");
    expect(register).toContain("Şifre (tekrar)");
  });

  it("renders the layout with navigation and each page's first state for a signed-in user", () => {
    signIn();
    const dashboard = render("/panel");
    for (const label of ["Panel", "Profil", "Asistan", "Portföy", "Piyasa (4.4)", "Çıkış", "demo.medium@ainvest.local"]) {
      expect(dashboard).toContain(label);
    }
    // the dashboard starts by loading the latest score
    expect(dashboard).toContain("Finansal IQ skorun yükleniyor");

    expect(render("/profil")).toContain("Profil yükleniyor");
    expect(render("/asistan")).toContain("Asistan");
    expect(render("/portfoy")).toContain("Portföy");
    expect(render("/piyasa")).toContain("Piyasa (4.4)");
  });

  it("does not render protected pages without a session", () => {
    const page = render("/asistan");
    expect(page).not.toContain("Çıkış");
    expect(page).not.toContain("Finansal IQ skorun yükleniyor");
  });

  it("renders the 404 page", () => {
    expect(render("/olmayan-sayfa")).toContain("Sayfa bulunamadı");
  });
});
