"""Compares the synthetic evaluation population with published Turkish shares (realism check).

    py -3 evaluation/realism_check.py                # out/clean.in.json: the 300 profiles of run_evaluation.py
    py -3 evaluation/realism_check.py --name clean

The advisor asked for realistic data instead of a purely synthetic evaluation. No open Turkish dataset
holds the score's seven inputs for the same person, so this check compares shares: every target is a
published Turkish figure (Findex 2025, TÜİK GYKA / Eurostat, TBB Risk Merkezi), and every measure is the
closest thing the synthetic profiles can compute. A survey question and the score's ratio are never the
same thing, so each row says how close the two are ("yakın" or "kaba") and which way the proxy leans.
Sources marked "ikincil" are news or aggregator copies and still need the official table.

Standard library only. Prints a table and writes out/realism_<name>.json.
"""

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"

# name, year, status, url
SOURCES = {
    "eurostat": ("Eurostat ilc_mdes04 (TÜİK GYKA ile aynı seri)", "2025", "birincil",
                 "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/ilc_mdes04"
                 "?format=JSON&lang=en&geo=TR&geo=EU27_2020"),
    "findex": ("Global Findex 2025, Little Data Book s. 147", "2025 (anket 2024)",
               "PDF metninden çıkarıldı; sayfada gözle teyit edilmeli",
               "https://thedocs.worldbank.org/en/doc/be6615202d1f08a25855c8ac2d615122-0050012025/related/"
               "Little-Data-Book-2025-Web.pdf"),
    "gyka_debt": ("TÜİK Yoksulluk ve Yaşam Koşulları 2025", "2025", "ikincil; tanımı doğrulanmadı",
                  "https://www.alomaliye.com/2025/12/30/goreli-yoksulluk-2025te-yuzde-13-0a-geriledi-tuik-"
                  "yoksulluk-ve-yasam-kosullari-verileri/"),
    "gyka_income": ("TÜİK Gelir Dağılımı 2025, eşdeğer fert sıralaması", "2025 (2024 geliri)", "ikincil",
                    "https://www.alomaliye.com/2025/12/26/gelir-dagilimi-istatistikleri-2025-en-zengin-yuzde-"
                    "20nin-payi-yuzde-48-0e-geriledi-gini-0-410-oldu/"),
    "risk_center": ("TBB Risk Merkezi Aylık Bülten", "Haziran 2026", "birincil",
                    "https://www.riskmerkezi.org/download/node/15155/field_raporlar_ekler/18712"),
    "saving_rate": ("TÜİK Kurumsal Sektör Hesapları", "2025", "ikincil",
                    "https://www.alomaliye.com/2026/10/08/gsmh-2025-yilinda-62-trilyon-288-milyar-tl-oldu/"),
}


def share(profiles: list[dict], predicate) -> float:
    return sum(1 for p in profiles if predicate(p)) / len(profiles) if profiles else 0.0


def cannot_cover_unexpected(p: dict) -> bool:
    # cash below one month of expenses; the survey's amount is smaller than that for most people,
    # so this over-counts and gives an upper bound for the synthetic share
    return p["cashReserve"] < p["monthlyExpenses"]


def lasts_over_two_months_cash(p: dict) -> bool:
    return p["cashReserve"] > 2 * p["monthlyExpenses"]


def lasts_over_two_months_all(p: dict) -> bool:
    # every investment counted as sellable at full value: an upper bound
    return p["cashReserve"] + p["investmentAmount"] > 2 * p["monthlyExpenses"]


def saves(p: dict) -> bool:
    return p["monthlyIncome"] - p["monthlyExpenses"] - p["monthlyDebtPayment"] > 0


def income_groups(profiles: list[dict]) -> tuple[list[dict], list[dict], list[dict]]:
    """Bottom 20%, the other 80% and the top 20% by monthly income."""
    ranked = sorted(profiles, key=lambda p: p["monthlyIncome"])
    k = len(ranked) // 5
    return ranked[:k], ranked[k:], ranked[-k:]


def income_share(group: list[dict], profiles: list[dict]) -> float:
    return sum(p["monthlyIncome"] for p in group) / sum(p["monthlyIncome"] for p in profiles)


def row(key: str, label: str, turkey: float, synthetic: float | None, unit: str, source: str,
        proxy: str, fit: str, note: str = "") -> dict:
    name, year, status, url = SOURCES[source]
    return {"key": key, "label": label, "turkey": turkey, "synthetic": synthetic, "unit": unit,
            "source": name, "year": year, "sourceStatus": status, "url": url,
            "proxy": proxy, "fit": fit, "note": note}


def compare(profiles: list[dict]) -> list[dict]:
    bottom, rest, top = income_groups(profiles)
    debtors = [p for p in profiles if p["totalDebt"] > 0]
    debts = [p["totalDebt"] for p in debtors]
    low_rate, rest_rate = share(bottom, cannot_cover_unexpected), share(rest, cannot_cover_unexpected)
    bottom_share, top_share = income_share(bottom, profiles), income_share(top, profiles)
    total_income = sum(p["monthlyIncome"] for p in profiles)
    total_expenses = sum(p["monthlyExpenses"] for p in profiles)
    total_installments = sum(p["monthlyDebtPayment"] for p in profiles)
    # national accounts count loan principal as saving and interest as neither, so the comparable synthetic
    # rate lies between "every installment spent" (shown) and "every installment saved" (in the note)
    saving_low = (total_income - total_expenses - total_installments) / total_income
    saving_high = (total_income - total_expenses) / total_income

    return [
        row("cannotCoverUnexpected", "Beklenmedik bir harcamayı karşılayamayanlar", 0.251,
            share(profiles, cannot_cover_unexpected), "share", "eurostat",
            "nakit rezerv < 1 aylık gider", "yakın",
            "Ölçü çoğu profil için üst sınır: ankette sorulan tutar bir aylık giderden küçük."),
        row("lastsOver2MonthsCash", "Gelir kesilirse 2 aydan uzun idare edebilenler (yalnız nakit)", 0.223,
            share(profiles, lasts_over_two_months_cash), "share", "findex",
            "nakit rezerv > 2 aylık gider", "yakın", "Yatırım sayılmadığı için alt sınır."),
        row("lastsOver2MonthsAll", "Gelir kesilirse 2 aydan uzun idare edebilenler (nakit + yatırım)", 0.223,
            share(profiles, lasts_over_two_months_all), "share", "findex",
            "nakit + yatırımın tamamı > 2 aylık gider", "yakın", "Yatırımın tamamı satılabilir sayıldığı için üst sınır."),
        row("saved", "Son yılda tasarruf edenler", 0.412,
            share(profiles, saves), "share", "findex",
            "gelir − gider − taksit > 0", "kaba",
            "Findex herhangi bir birikimi soruyor; aylık artısı olan biri büyük olasılıkla birikim yapmıştır."),
        row("hasInstallment", "Borç ya da taksit ödemesi olanlar", 0.564,
            share(profiles, lambda p: p["monthlyDebtPayment"] > 0), "share", "gyka_debt",
            "aylık taksit > 0", "yakın", "Konut kredisi dahil mi, kişi mi hane mi bilinmiyor."),
        row("hasDebt", "Son yılda borçlananlar", 0.647,
            share(profiles, lambda p: p["totalDebt"] > 0), "share", "findex",
            "toplam borç > 0", "kaba", "Findex akışı (son yılda borç aldı mı), sentetik veri stoku ölçüyor."),
        row("debtPerDebtor", "Borçlu başına ortalama borç", 156_000,
            statistics.mean(debts) if debts else None, "tl", "risk_center",
            "borcu olanların ortalama toplam borcu", "yakın",
            f"Sentetik medyan {fmt(statistics.median(debts), 'tl')}. Risk Merkezi banka kredilerini (kart ve konut "
            "dahil) kişi başına sayıyor." if debts else ""),
        row("incomeBottom20", "Gelirin en alt %20'ye düşen payı", 0.064,
            bottom_share, "share", "gyka_income",
            "en düşük gelirli %20 profilin gelir payı", "yakın", "Sentetik gelir kişi geliri, TÜİK eşdeğer fert geliri."),
        row("incomeTop20", "Gelirin en üst %20'ye düşen payı", 0.480,
            top_share, "share", "gyka_income",
            "en yüksek gelirli %20 profilin gelir payı", "yakın"),
        row("s80s20", "En üst %20 / en alt %20 gelir payı oranı", 7.5,
            top_share / bottom_share, "ratio", "gyka_income",
            "üst %20 payı / alt %20 payı", "yakın"),
        row("savingRate", "Hanehalkı tasarruf oranı", 0.143,
            saving_low, "share", "saving_rate",
            "(Σ gelir − Σ gider − Σ taksit) / Σ gelir", "kaba",
            f"Ulusal hesapta taksidin anapara kısmı tasarruf sayılıyor; taksidin tamamı tasarruf sayılırsa sentetik oran "
            f"{fmt(saving_high, 'share')}. Karşılaştırılabilir değer bu iki ucun arasında."),
        row("incomeGradient", "Karşılayamayanlar: düşük gelirli / diğerleri", 0.587 / 0.148,
            low_rate / rest_rate if rest_rate else None, "ratio", "eurostat",
            "en alt %20 gelirde karşılayamayan payı / kalan %80'deki pay", "kaba",
            f"Türkiye: yoksulluk sınırı altında %58,7, üstünde %14,8. Sentetik: en alt %20'de "
            f"{fmt(low_rate, 'share')}, kalanlarda {fmt(rest_rate, 'share')}."),
    ]


def extras(profiles: list[dict], scored: list[dict]) -> dict:
    incomes = [p["monthlyIncome"] for p in profiles]
    by_archetype = {}
    for kind in sorted({p.get("archetype", "-") for p in profiles}):
        group = [p for p in profiles if p.get("archetype", "-") == kind]
        by_archetype[kind] = {
            "profiles": len(group),
            "cannotCoverUnexpected": share(group, cannot_cover_unexpected),
            "lastsOver2MonthsCash": share(group, lasts_over_two_months_cash),
            "saved": share(group, saves),
            "hasInstallment": share(group, lambda p: p["monthlyDebtPayment"] > 0),
        }
    result = {
        "monthlyIncome": {"min": min(incomes), "mean": statistics.mean(incomes), "max": max(incomes)},
        "withInvestment": share(profiles, lambda p: p["investmentAmount"] > 0),
        "byArchetype": by_archetype,
    }
    if scored:
        def reserve_points(s: dict) -> int:
            breakdown = s["factorBreakdown"]
            if isinstance(breakdown, str):
                breakdown = json.loads(breakdown)
            return breakdown["factors"]["CashReserveMonths"]
        result["segments"] = {k: v / len(scored) for k, v in sorted(Counter(s["segment"] for s in scored).items())}
        result["reservePointsAtLeast15"] = share(scored, lambda s: reserve_points(s) >= 15)
    return result


def fmt(value: float | None, unit: str) -> str:
    if value is None:
        return "—"
    if unit == "share":
        text = f"{value * 100:.1f}".replace(".", ",")
        return "%" + (text[:-2] if text.endswith(",0") else text)
    if unit == "tl":
        return f"{value:,.0f} TL".replace(",", ".")
    return f"{value:.1f} kat".replace(".", ",")


def print_report(result: dict) -> None:
    print(f"Sentetik nüfus: {result['population']} ({result['profiles']} profil)\n")
    print("| # | Gösterge | Türkiye | Sentetik | Uyum | Kaynak |")
    print("|---|---|---|---|---|---|")
    for i, r in enumerate(result["rows"], 1):
        print(f"| {i} | {r['label']} | {fmt(r['turkey'], r['unit'])} | {fmt(r['synthetic'], r['unit'])} "
              f"| {r['fit']} | {r['source']}, {r['year']} ({r['sourceStatus']}) |")
    print("\nÖlçüler:")
    for i, r in enumerate(result["rows"], 1):
        print(f" {i}. {r['proxy']}. {r['note']}".rstrip())
    e = result["extras"]
    print("\nEk gözlemler:")
    print(f" - Aylık gelir: {fmt(e['monthlyIncome']['min'], 'tl')} – {fmt(e['monthlyIncome']['max'], 'tl')}, "
          f"ortalama {fmt(e['monthlyIncome']['mean'], 'tl')}")
    print(f" - Yatırımı olan profiller: {fmt(e['withInvestment'], 'share')}")
    for kind, g in e["byArchetype"].items():
        print(f" - {kind} ({g['profiles']}): karşılayamayan {fmt(g['cannotCoverUnexpected'], 'share')}, "
              f"2 aydan uzun (nakit) {fmt(g['lastsOver2MonthsCash'], 'share')}, "
              f"tasarruf eden {fmt(g['saved'], 'share')}, taksidi olan {fmt(g['hasInstallment'], 'share')}")
    if "segments" in e:
        print(" - Segmentler: " + ", ".join(f"{k} {fmt(v, 'share')}" for k, v in e["segments"].items()))
        print(f" - Rezerv faktöründen en az 15 puan (≥ 3 ay) alanlar: {fmt(e['reservePointsAtLeast15'], 'share')}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--name", default="clean", help="population file out/<name>.in.json (default: clean)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    profiles = json.loads((OUT / f"{args.name}.in.json").read_text(encoding="utf-8"))
    scored_path = OUT / f"{args.name}.scored.json"
    scored = json.loads(scored_path.read_text(encoding="utf-8")) if scored_path.exists() else []
    result = {"population": args.name, "profiles": len(profiles),
              "rows": compare(profiles), "extras": extras(profiles, scored)}
    (OUT / f"realism_{args.name}.json").write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print_report(result)


if __name__ == "__main__":
    main()
