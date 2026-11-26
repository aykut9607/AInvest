import type { ReactNode } from "react";
import { renderToString } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { saveProfile } from "../../api/financeApi";
import { clearSession, setSession } from "../../api/session";
import { ProfileForm } from "../../pages/ProfilePage";
import { MemoryStorage, json, makeJwt, mockFetch } from "../../test/helpers";
import type { FinancialProfile, ProfileInput } from "../../types/api";
import { PaymentHabitsView } from "./PaymentHabitsCard";

const inRouter = (node: ReactNode) => renderToString(<MemoryRouter>{node}</MemoryRouter>);

const PROFILE: FinancialProfile = {
  id: "p1",
  userId: "u-1",
  monthlyIncome: 40000,
  monthlyExpenses: 20000,
  monthlyDebtPayment: 3000,
  totalDebt: 50000,
  cashReserve: 60000,
  investmentAmount: 10000,
  riskPreference: null,
  impatienceLevel: 2,
  billsOnTime: "ALMOST_ALL",
  minimumPaymentMonths: "NO_CARD",
  latePayments: null,
  createdAt: "2026-11-01T00:00:00Z",
  updatedAt: "2026-11-01T00:00:00Z",
};

const INPUT: ProfileInput = {
  monthlyIncome: 40000,
  monthlyExpenses: 20000,
  monthlyDebtPayment: 3000,
  totalDebt: 50000,
  cashReserve: 60000,
  investmentAmount: 10000,
  impatienceLevel: 2,
};

describe("payment habits", () => {
  beforeEach(() => {
    vi.stubGlobal("sessionStorage", new MemoryStorage());
    setSession({ accessToken: makeJwt({ sub: "u-1" }), refreshToken: "r", userId: "u-1", email: "a@b.c" });
  });
  afterEach(() => {
    clearSession();
    vi.unstubAllGlobals();
  });

  it("saveProfile sends only the answered habits", async () => {
    const { calls } = mockFetch(() => json(200, { data: null, success: true, message: "" }));
    await saveProfile({ ...INPUT, billsOnTime: "MOST", minimumPaymentMonths: null, latePayments: "ONCE" });
    await saveProfile(INPUT);

    expect(calls[0].body).toMatchObject({ billsOnTime: "MOST", latePayments: "ONCE" });
    expect(calls[0].body).not.toHaveProperty("minimumPaymentMonths");
    for (const key of ["billsOnTime", "minimumPaymentMonths", "latePayments"]) expect(calls[1].body).not.toHaveProperty(key);
  });

  it("the profile form has the optional fieldset and reloads saved answers", () => {
    const html = inRouter(<ProfileForm profile={PROFILE} />);
    expect(html).toContain("Ödeme alışkanlıkları (isteğe bağlı)");
    expect(html).toContain("Bu cevaplar şimdilik skoru değiştirmez; ileride skora eklenecek.");
    expect(html).toMatch(/name="billsOnTime" checked="" value="ALMOST_ALL"/);
    expect(html).toMatch(/name="minimumPaymentMonths" checked="" value="NO_CARD"/);
    expect(html).toMatch(/name="latePayments" checked="" value=""/);
    expect(html).toContain("Boş bırak");
  });

  it("the dashboard card shows the answers, or an empty state linking to the profile", () => {
    const answered = inRouter(<PaymentHabitsView habits={PROFILE} />);
    expect(answered).toContain("Neredeyse hepsini");
    expect(answered).toContain("Kredi kartım yok");
    expect(answered).toContain("Cevaplanmadı");

    const empty = inRouter(<PaymentHabitsView habits={{ billsOnTime: null }} />);
    expect(empty).toContain('data-testid="payment-habits-empty"');
    expect(empty).toContain('href="/profil"');
  });
});
