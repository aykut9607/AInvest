"""Creates demo users with one Financial IQ scenario each, through the Edge Gateway.

Every account goes through the real flow (register/login at Identity, profile at Finance, IQ via Finance),
so the data is the same on every machine and the AI tools can be tried with a real token.

Needs: Identity (8081), Finance Profile (5293), Financial IQ (5109) and Edge Gateway (5000) running.
Run from the repo root (standard library only, no venv needed):

    python infra/seed/seed_demo_users.py

Safe to run again: an existing account is logged in instead of registered, and the profile is overwritten.
All demo accounts use the password below (local development only).

The expected scores depend on the scoring version the IQ service runs (factorBreakdown.version of each result),
so the script checks a v2 and a v3 service alike. v3 values: evaluation/IQ_V3_PROPOSAL.md 6.1 (variant v3c-i5),
the same numbers the IQ tests check (GoldenTableTests).
"""

import base64
import json
import sys
import time
import urllib.error
import urllib.request

GATEWAY = "http://localhost:5000"
PASSWORD = "Demo12345!"


def profile(income, expenses, payment=0, debt=0, cash=0, investments=0, impatience=3):
    return {
        "monthlyIncome": income,
        "monthlyExpenses": expenses,
        "monthlyDebtPayment": payment,
        "totalDebt": debt,
        "cashReserve": cash,
        "investmentAmount": investments,
        "impatienceLevel": impatience,
    }


# email, what it shows, profiles in order (more than one -> score history / trend),
# expected (score, appliedRule) of every calculation, per scoring version
SCENARIOS = [
    ("demo.low@ainvest.local", "LOW: low reserve, negative savings, overspending, impatient (sample profile)",
     [profile(30000, 25000, 7000, 90000, 3000, 10000, 5)],
     {"v2": [(8, None)], "v3": [(27, None)]}),
    ("demo.medium@ainvest.local", "2 months reserve, 16% installment, 24% savings (v2 MEDIUM; v3 HIGH 71, "
     "'Installment without debt': no total debt entered)",
     [profile(50000, 30000, 8000, 0, 60000, 0, 3)],
     {"v2": [(62, None)], "v3": [(71, None)]}),
    ("demo.high@ainvest.local", "HIGH: healthy ratios, no rule (v3: 'Installment without debt', no total debt entered)",
     [profile(20000, 8000, 2000, 0, 30000, 0, 2)],
     {"v2": [(88, None)], "v3": [(87, None)]}),
    ("demo.highdebt@ainvest.local", "'High total debt': small installment hides a debt of 4 years of income "
     "(v2 MEDIUM; v3 LOW, the installment is below the interest)",
     [profile(40000, 16000, 2000, 2000000, 50000, 0, 2)],
     {"v2": [(63, None)], "v3": [(22, None)]}),
    ("demo.richincome@ainvest.local", "1,000,000 a month, no cash yet (v2 VERY_HIGH_INCOME -> 100; v3 scored by the ratios)",
     [profile(1000000, 900000, 0, 0, 0, 0, 5)],
     {"v2": [(100, "VERY_HIGH_INCOME")], "v3": [(53, None)]}),
    ("demo.richwealth@ainvest.local", "small salary, 10,000,000 net worth (v2 VERY_HIGH_WEALTH -> 100; v3 WEALTH_RUNWAY)",
     [profile(30000, 29000, 0, 1000000, 2000000, 9000000, 5)],
     {"v2": [(100, "VERY_HIGH_WEALTH")], "v3": [(84, "WEALTH_RUNWAY")]}),
    ("demo.extremedebt@ainvest.local", "net debt over 100,000,000 (v2 EXTREME_DEBT -> 0; v3 SOLVENCY_CAP -> 0)",
     [profile(40000, 16000, 4000, 120000000, 96000, 10000000, 1)],
     {"v2": [(0, "EXTREME_DEBT")], "v3": [(0, "SOLVENCY_CAP")]}),
    ("demo.trend@ainvest.local", "Trend: 4 calculations, finances improve step by step (for /history)",
     [profile(30000, 25000, 7000, 90000, 3000, 10000, 5),
      profile(30000, 22000, 5000, 70000, 15000, 10000, 4),
      profile(30000, 18000, 4000, 50000, 45000, 15000, 3),
      profile(30000, 15000, 3000, 30000, 90000, 20000, 2)],
     {"v2": [(8, None), (37, None), (62, None), (92, None)],
      "v3": [(27, None), (51, None), (79, None), (97, None)]}),
]


def call(method, path, body=None, token=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(GATEWAY + path, data=data, method=method)
    request.add_header("Content-Type", "application/json")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            text = response.read().decode()
            return response.status, json.loads(text) if text else None
    except urllib.error.HTTPError as error:
        text = error.read().decode()
        try:
            return error.code, json.loads(text) if text else None
        except json.JSONDecodeError:
            return error.code, text
    except urllib.error.URLError as error:
        sys.exit(f"Cannot reach the gateway at {GATEWAY} ({error.reason}). Are the services running?")


def user_id_from(token):
    # reads the "sub" claim without checking the signature (the gateway checks it)
    payload = token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    return json.loads(base64.urlsafe_b64decode(payload))["sub"]


def sign_in(email):
    status, body = call("POST", "/auth/register", {"email": email, "password": PASSWORD})
    if status == 409:  # already registered on this machine
        status, body = call("POST", "/auth/login", {"email": email, "password": PASSWORD})
        while status == 429:  # the gateway allows 5 logins a minute and there are more accounts than that
            print(f"{email}: login limit reached, waiting 15 seconds")
            time.sleep(15)
            status, body = call("POST", "/auth/login", {"email": email, "password": PASSWORD})
    if status != 200 or not body or "accessToken" not in body:
        sys.exit(f"{email}: sign-in failed ({status}): {body}")
    return body["accessToken"]


def main():
    rows = []
    failures = 0
    for email, description, profiles, expected_by_version in SCENARIOS:
        token = sign_in(email)
        user_id = user_id_from(token)
        results = []
        for item in profiles:
            status, body = call("PUT", f"/api/Profiles/{user_id}", item, token)
            if status != 200:
                sys.exit(f"{email}: saving the profile failed ({status}): {body}")
            status, body = call("POST", f"/api/Profiles/{user_id}/calculate-iq", None, token)
            if status != 200:
                sys.exit(f"{email}: calculating the IQ failed ({status}): {body}")
            results.append(body["data"])

        # the scoring version the service used (v1 results carried no version)
        version = results[-1]["factorBreakdown"].get("version") or "v1"
        got = [(r["score"], r["factorBreakdown"].get("appliedRule")) for r in results]
        expected = expected_by_version.get(version)
        mark = ""
        if expected is None:
            mark = f"  <-- no expected scores for scoring version {version}"
            failures += 1
        elif got != expected:
            mark = f"  <-- expected {' -> '.join(str(e) for e in expected)}"
            failures += 1
        result = results[-1]
        scores = " -> ".join(str(score) for score, _ in got)
        rows.append((email, user_id, scores, result["segment"], got[-1][1] or "-", version, description, mark))

    print(f"Password for all demo accounts: {PASSWORD}\n")
    for email, user_id, scores, segment, rule, version, description, mark in rows:
        print(f"{email:32} {scores:>3} {segment:6} {rule:16} {version:3} {user_id}{mark}")
        print(f"{'':32} {description}")
    if failures:
        sys.exit(f"\n{failures} scenario(s) did not give the expected score")


if __name__ == "__main__":
    main()
