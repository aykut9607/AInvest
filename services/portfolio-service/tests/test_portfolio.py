"""4.1-4.3: allocation rules and the HTTP endpoints (SQLite in memory, fake Finance and IQ services)."""

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from adapters.upstream import Upstream, get_upstream
from core.config import get_settings
from db import models  # noqa: F401
from db.session import Base, get_session
from main import app
from services import allocation as al
from services.baskets import ASSET_LABELS, ASSETS, INSTITUTION_BASKETS, INSTITUTION_LABELS, INSTITUTION_SOURCES, MEASURED_VOLATILITY, RISKY_ASSETS, RISKY_SHARE, SAFE_ASSETS

HIGH_USER = dict(monthlyIncome=20000, monthlyExpenses=8000, monthlyDebtPayment=2000, totalDebt=10000, cashReserve=30000, investmentAmount=0)


def profile(**changes):
    d = HIGH_USER | changes
    return al.Profile(d["monthlyIncome"], d["monthlyExpenses"], d["monthlyDebtPayment"], d["totalDebt"], d["cashReserve"], d["investmentAmount"], d.get("impatienceLevel", 2))


def risky(weights):
    return sum(w for a, w in weights.items() if a in RISKY_ASSETS)


# ---------- how much

def test_the_schema_example():
    i = al.investable(88, None, profile())
    assert (i.share_percent, i.monthly_amount, i.one_time_amount, i.reasons) == (58, 5800, 3480, ())


@pytest.mark.parametrize(("score", "share"), [(0, 0), (30, 0), (50, 20), (70, 40), (100, 70)])
def test_share_follows_the_score(score, share):
    assert al.investable(score, None, profile()).share_percent == share


def test_no_share_without_the_emergency_fund_except_for_the_full_score_rules():
    poor = profile(cashReserve=10000)
    assert al.investable(88, None, poor).share_percent == 0
    assert "RESERVE_FIRST" in al.investable(88, None, poor).reasons
    assert al.investable(100, "VERY_HIGH_INCOME", poor).share_percent == 70
    assert al.investable(100, "VERY_HIGH_WEALTH", poor).one_time_amount == 0          # never a negative amount


def test_the_reserve_counts_half_of_the_investments_like_the_score_does():
    assert al.investable(88, None, profile(cashReserve=10000, investmentAmount=28000)).share_percent == 58          # 10,000 + 14,000 = 3 x 8,000
    assert al.investable(88, None, profile(cashReserve=10000, investmentAmount=27000)).share_percent == 0


def test_a_monthly_gap_gives_zero_not_a_negative_amount():
    i = al.investable(88, None, profile(monthlyExpenses=19000, cashReserve=100000))
    assert i.monthly_amount == 0 and "NO_MONTHLY_SURPLUS" in i.reasons


def test_net_debt_is_a_warning_not_a_lock():
    i = al.investable(88, None, profile(totalDebt=40000))
    assert "DEBT_FIRST" in i.reasons and i.share_percent == 58


def test_risk_above_the_ceiling_is_refused():
    al.check_risk("MEDIUM", "MEDIUM")
    with pytest.raises(al.AllocationError):
        al.check_risk("HIGH", "MEDIUM")


@pytest.mark.parametrize(("changes", "ceiling", "why"), [
    ({}, "HIGH", ()),                                                                             # healthy: the segment decides
    ({"cashReserve": 20000, "investmentAmount": 0}, "LOW", ("CEILING_RESERVE",)),                # 2.5 months of reserve
    ({"cashReserve": 0, "investmentAmount": 60000}, "HIGH", ()),                                  # half of the investments counts, as in the IQ
    ({"monthlyExpenses": 13000, "monthlyDebtPayment": 7000, "cashReserve": 60000}, "LOW", ("CEILING_NO_SURPLUS",)),          # nothing left at the end of the month
    ({"monthlyDebtPayment": 7300}, "MEDIUM", ("CEILING_DEBT",)),                                 # installment 36.5 % of income
    ({"totalDebt": 800000}, "MEDIUM", ("CEILING_DEBT",)),                                        # net debt more than 3 years of income
    ({"impatienceLevel": 5}, "MEDIUM", ("CEILING_IMPATIENCE",)),
    ({"impatienceLevel": 4, "monthlyDebtPayment": 7300}, "LOW", ("CEILING_DEBT", "CEILING_IMPATIENCE")),
])
def test_the_weakest_link_lowers_the_ceiling(changes, ceiling, why):
    assert al.risk_ceiling("HIGH", None, profile(**changes)) == (ceiling, why)


def test_the_ceiling_never_rises_above_the_segment_and_the_rich_keep_theirs():
    assert al.risk_ceiling("LOW", None, profile()) == ("LOW", ())
    assert al.risk_ceiling("LOW", None, profile(impatienceLevel=5)) == ("LOW", ())          # there is no lower level
    poor_cash = profile(monthlyIncome=1000000, monthlyExpenses=900000, cashReserve=0, investmentAmount=0)
    assert al.risk_ceiling("HIGH", "VERY_HIGH_INCOME", poor_cash) == ("HIGH", ())
    assert al.risk_ceiling("HIGH", None, poor_cash)[0] == "LOW"
    assert al.risk_ceiling("MEDIUM", None, profile(monthlyIncome=0, monthlyExpenses=0, monthlyDebtPayment=0))[0] == "LOW"
    retiree = profile(monthlyIncome=0, monthlyExpenses=15000, monthlyDebtPayment=0, totalDebt=0, cashReserve=1000000, investmentAmount=5000000)
    assert al.risk_ceiling("HIGH", None, retiree, "WEALTH_FLOOR") == ("HIGH", ())          # IQ v2.1 raised the score by the wealth itself
    assert al.risk_ceiling("HIGH", None, retiree)[0] == "LOW"
    earner = profile(monthlyIncome=999999, monthlyExpenses=990000, cashReserve=0, investmentAmount=0)
    assert al.investable(99, None, earner, "INCOME_FLOOR").share_percent == 69 and al.investable(99, None, earner).share_percent == 0


# ---------- in what

@pytest.mark.parametrize("style", INSTITUTION_BASKETS)
@pytest.mark.parametrize("risk", RISKY_SHARE)
def test_published_allocations_add_up_and_carry_their_source(style, risk):
    b = al.institution(style, risk)
    assert sum(b.weights.values()) == pytest.approx(100, abs=0.02)
    assert b.source["url"].startswith("https://") and set(INSTITUTION_SOURCES) == set(INSTITUTION_BASKETS)
    assert sum(al.percentages(b.weights).values()) == pytest.approx(100)


@pytest.mark.parametrize("risk", RISKY_SHARE)
def test_standard_basket_risky_share_and_equal_safe_part(risk):
    w = al.standard(risk).weights
    assert risky(w) == pytest.approx(RISKY_SHARE[risk])
    assert len({round(w[a], 6) for a in SAFE_ASSETS}) == 1
    assert w["SPX"] / w["BTC"] == pytest.approx(MEASURED_VOLATILITY["BTC"] / MEASURED_VOLATILITY["SPX"])


def test_excluded_asset_stays_in_its_own_part():
    b = al.standard("MEDIUM", ("BTC",))
    assert b.weights["SPX"] + b.weights["NVDA"] == pytest.approx(50)
    assert b.weights["SPX"] / b.weights["NVDA"] == pytest.approx(MEASURED_VOLATILITY["NVDA"] / MEASURED_VOLATILITY["SPX"])
    assert b.reasons == ["EXCLUDED_ASSET_REPLACED:BTC->SPX", "EXCLUDED_ASSET_REPLACED:BTC->NVDA"]
    assert risky(al.standard("HIGH", ("BTC", "SPX", "NVDA")).weights) == 0
    with pytest.raises(al.AllocationError):
        al.standard("LOW", SAFE_ASSETS)


def test_low_risk_user_cannot_get_a_bitcoin_portfolio():
    b = al.custom("LOW", ("BTC",))
    assert b.weights["BTC"] == pytest.approx(20) and "SPX" not in b.weights          # the chosen asset fills the ceiling first
    assert "RISK_CEILING_REACHED" in b.reasons and sum(b.weights.values()) == pytest.approx(100)


@pytest.mark.parametrize("risk", RISKY_SHARE)
@pytest.mark.parametrize("focus", [("BTC",), ("GOLD",), ("SPX", "NVDA"), ("GOLD", "BTC"), ("BTC", "SPX", "NVDA", "BIST"), SAFE_ASSETS])
@pytest.mark.parametrize("excluded", [(), ("EUR",)])
def test_custom_never_exceeds_the_ceiling_and_always_adds_up(risk, focus, excluded):
    if set(focus) & set(excluded):
        with pytest.raises(al.AllocationError):
            al.custom(risk, focus, excluded)
        return
    w = al.custom(risk, focus, excluded).weights
    assert sum(w.values()) == pytest.approx(100) and risky(w) <= RISKY_SHARE[risk] + 1e-6
    assert all(v >= 0 for v in w.values()) and not set(excluded) & set(w)


def test_custom_focus_takes_the_largest_part_when_the_risk_allows():
    w = al.custom("HIGH", ("SPX",)).weights
    assert w["SPX"] >= 60 and w["SPX"] == max(w.values())


def test_every_asset_and_style_has_a_name_for_the_screen():
    used = set(ASSETS) | {a for style in INSTITUTION_BASKETS.values() for w in style.values() for a in w}
    assert used <= set(ASSET_LABELS) and set(INSTITUTION_LABELS) == set(INSTITUTION_BASKETS)


def test_reason_codes_are_the_ones_the_ai_service_reads():
    import re
    for b in (al.standard("MEDIUM", ("BTC", "EUR")), al.standard("HIGH", ("BTC", "SPX"))):
        assert all(re.fullmatch(r"EXCLUDED_ASSET_REPLACED:[A-Z0-9_]{1,24}->[A-Z0-9_]{1,24}", r) for r in b.reasons)


def test_rounding_is_exact():
    p = al.percentages({"A": 1, "B": 1, "C": 1})
    assert sum(p.values()) == pytest.approx(100) and sorted(p.values()) == [33.33, 33.33, 33.34]
    assert sum(al.amounts(p, 1000.01).values()) == pytest.approx(1000.01)


# ---------- endpoints

class FakeServices:
    def __init__(self):
        self.profile, self.score, self.segment, self.version, self.down = dict(HIGH_USER), 88, "HIGH", 7, False

    def __call__(self, request: httpx.Request) -> httpx.Response:
        if self.down:
            raise httpx.ConnectError("down")
        if "/api/Profiles/" in request.url.path:
            return httpx.Response(200, json={"data": self.profile, "success": True, "message": ""}) if self.profile else httpx.Response(404, json={"data": None})
        return httpx.Response(200, json={"success": True, "message": "", "data": {"score": self.score, "segment": self.segment, "resultVersion": self.version,
                                         "createdAt": "2026-11-25T10:00:00", "updatedAt": "2026-11-25T11:00:00", "factorBreakdown": {"version": "v2", "appliedRule": None}}})


@pytest.fixture
def services(client):
    fake = FakeServices()
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)

    def session():
        with sessionmaker(bind=engine)() as s:
            yield s

    app.dependency_overrides[get_session] = session
    app.dependency_overrides[get_upstream] = lambda: Upstream(get_settings(), httpx.MockTransport(fake))
    return fake


ME, URL = {"X-User-Id": "u1"}, "/api/portfolio/u1"


def choose(client, **body):
    return client.put(f"{URL}/preferences", json={"option": "STANDARD", "riskLevel": "MEDIUM"} | body, headers=ME)


def test_options(client, services):
    d = client.get(f"{URL}/options", headers=ME).json()["data"]
    assert d["maxRisk"] == "HIGH" and d["unavailableOptions"] == ["AINVEST"]
    assert d["investable"] == {"sharePercent": 58, "monthlyAmount": 5800, "oneTimeAmount": 3480}


def test_only_the_owner_and_only_through_the_gateway(client, services):
    assert client.get(f"{URL}/options").status_code == 401
    assert client.get(f"{URL}/options", headers={"X-User-Id": "u2"}).status_code == 403


def test_choose_propose_read(client, services):
    assert client.get(f"{URL}/latest", headers=ME).status_code == 404
    assert client.post(f"{URL}/proposal", headers=ME).status_code == 404
    assert choose(client, option="INSTITUTION", institutionStyle="YAPIKREDI").status_code == 200
    made = client.post(f"{URL}/proposal", headers=ME).json()["data"]
    assert made["source"]["period"] == "2026-10"
    assert sum(a["percent"] for a in made["allocations"]) == pytest.approx(100)
    assert sum(a["amount"] for a in made["allocations"]) == pytest.approx(5800)
    read = client.get(f"{URL}/latest", headers=ME).json()["data"]
    assert read["proposalId"] == made["proposalId"] and read["stale"] is False


def test_a_new_iq_result_makes_the_proposal_stale(client, services):
    choose(client)
    client.post(f"{URL}/proposal", headers=ME)
    services.version = 8
    assert client.get(f"{URL}/latest", headers=ME).json()["data"]["stale"] is True


def test_locked_risk_is_400_also_when_the_score_falls_later(client, services):
    assert choose(client, riskLevel="HIGH").status_code == 200
    services.score, services.segment = 50, "MEDIUM"
    assert choose(client, riskLevel="HIGH").status_code == 400
    assert client.post(f"{URL}/proposal", headers=ME).status_code == 400


def test_impossible_choices_are_400(client, services):
    assert choose(client, option="INSTITUTION").status_code == 400
    assert choose(client, option="CUSTOM").status_code == 400
    assert choose(client, option="CUSTOM", focusAssets=["DOGE"]).status_code == 400
    assert choose(client, excludedAssets=["TRY_DEPOSIT", "GOLD", "EUR"]).status_code == 400


def test_fields_of_another_option_are_refused_not_ignored(client, services):
    assert choose(client, option="INSTITUTION", institutionStyle="ISBANK", excludedAssets=["GOLD"]).status_code == 400
    assert choose(client, focusAssets=["BTC"]).status_code == 400
    assert choose(client, institutionStyle="ISBANK").status_code == 400


def test_every_error_has_the_same_shape(client, services):
    answers = [client.get(f"{URL}/options"), client.get(f"{URL}/options", headers={"X-User-Id": "u2"}), choose(client, option="XX"), choose(client, extra=1),
               client.put(f"{URL}/preferences", content=b"{", headers=ME), client.get(f"{URL}/latest", headers=ME)]
    assert [r.status_code for r in answers] == [401, 403, 400, 400, 400, 404]
    assert all(set(r.json()) == {"data", "success", "message"} and r.json()["success"] is False and r.json()["message"] for r in answers)


def test_the_ainvest_option_is_not_ready_yet(client, services):
    assert choose(client, option="AINVEST").status_code == 200
    assert client.post(f"{URL}/proposal", headers=ME).status_code == 409


def test_missing_profile_is_404_and_a_dead_service_is_502(client, services):
    services.profile = None
    assert client.get(f"{URL}/options", headers=ME).status_code == 404
    services.down = True
    assert client.get(f"{URL}/options", headers=ME).status_code == 502
