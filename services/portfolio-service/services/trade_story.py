"""What a virtual trade did, in two voices: for a trader and for everyone else. Deterministic: every number comes from the ledger. The AI service may
only rephrase these sentences (it never computes); if the model is off, they are shown as they are."""

PLAIN = {
    "Elliott": "dalga sayımı bir hareketin bitmiş olabileceğini gösterdi",
    "Harmonik": "fiyat bilinen bir dönüş şeklini tamamladı",
    "Fibonacci": "fiyat önceki hareketin oran hedefine ulaştı",
    "Uyumsuzluk": "fiyat yeni uç yaparken hareketin gücü azaldı",
    "SFP": "fiyat önceki ucu kısa süre geçip geri döndü",
    "Smart money": "fiyat daha önce güçlü alım ya da satım görülen bölgeye geldi",
    "EXT bandı": "fiyat haftalık aralığın dışındaki taşma bölgesine geldi",
    "Hacim profili": "fiyat geçmişte çok işlem gören bir seviyeye değdi",
    "Önceki dönem": "fiyat önceki dönemin önemli bir seviyesine değdi",
    "Key level": "fiyat henüz test edilmemiş önemli bir seviyeye değdi",
    "Price action": "mum ve grafik şekilleri dönüşü destekledi",
    "Funding": "kaldıraçlı işlemlerde bir yön aşırı kalabalıklaştı",
}
KIND = {"SCALP": "scalp", "SCALP_SWING": "scalp (swing ihtimalli)", "SWING": "swing"}


def zone(kind: str) -> str:
    if kind.startswith("HALF"):
        return "yarı kâr" + (f" ({kind[8:].replace('_', ' ')})" if kind.startswith("HALF_AT_") else " (+%50)")
    return {"STOP": "stop", "ENTRY_STOP": "girişteki stop", "MARKET_SELL": "market sell"}.get(kind, kind.replace("_", " "))


def num(v: float, digits: int = 2) -> str:
    return f"{v:,.{digits}f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def signed(v: float, digits: int = 2) -> str:
    return ("+" if v >= 0 else "−") + num(abs(v), digits)


def rule(tag: str) -> str:
    category, name, variant = (tag.split("|") + ["", ""])[:3]
    return f"{category}: {name}" + (f" ({variant})" if variant else "")


def facts(r: dict) -> dict:
    """The numbers both voices may use; a language model may not use any other."""
    found = {f: [rule(t) for t in tags] for f, tags in r["confirmations"].items()}
    counted = [{"category": c, "frame": v["frame"], "rule": rule(v["rule"]), "points": v["points"]} for c, v in r["categories"].items()]
    return {"asset": r["asset"], "direction": r["direction"], "kind": r["kind"], "status": r["status"], "openedAtTsi": r["openedAtTsi"], "closedAtTsi": r["closedAtTsi"], "durationHours": r["durationHours"],
            "entry": r["entry"], "stop": r["stop"], "stopPercent": r["stopPercent"], "leverage": r["leverage"], "marginUsd": r["marginUsd"], "score": r["score"], "triggerFrame": r["triggerFrame"],
            "trigger": [rule(t) for t in r["trigger"]], "counted": counted, "confirmationCount": sum(len(v) for v in found.values()), "confirmations": found,
            "takeProfits": r["takeProfits"], "stopped": r["stopped"], "pnlUsd": r["pnlUsd"], "roiPercent": r["roiPercent"], "resultR": r["resultR"], "maxProfit": r["maxProfit"], "maxLoss": r["maxLoss"],
            "unitsLeft": r["unitsLeft"], "stopNow": r["stopNow"], "openPnlUsd": r["openPnlUsd"], "evidence": {"proven": r["evidence"].get("proven", False)}}


def _exit(r: dict) -> str:
    taken = ", ".join(f"{zone(x['zone'])} {num(x['price'])} (%{x['units']:g})" for x in r["takeProfits"])
    parts = [f"Kâr alınan bölgeler: {taken}." if taken else "Kâr bölgesine ulaşmadı."]
    if r["stopped"]:
        parts.append(f"{'Pozisyonun tamamı' if not taken else 'Kalan %' + format(r['stopped']['units'], 'g')} {zone(r['stopped']['zone'])} ile {num(r['stopped']['price'])}'den kapandı ({signed(r['stopped']['pnlUsd'])} $).")
    elif r["status"] != "CLOSED":
        parts.append(f"Pozisyonun %{r['unitsLeft']:g}'i açık; stop {num(r['stopNow'])}, açık sonuç {signed(r['openPnlUsd'])} $.")
    return " ".join(parts)


def trader(r: dict) -> str:
    counted = "; ".join(f"{v['frame']} {rule(v['rule'])} {num(v['points'], 1)}" for v in r["categories"].values())
    result = f" Sonuç {signed(r['pnlUsd'])} $" + (f" ({signed(r['resultR'])}R, teminata göre %{signed(r['roiPercent'], 1)})." if r["resultR"] is not None else " (gerçekleşen kısım).")
    return (f"{r['asset']} {r['direction']} {KIND[r['kind']]}, {r['leverage']}x. Tetik {r['triggerFrame']}: {', '.join(rule(t) for t in r['trigger']) or 'uyumsuzluk'}. Puan {num(r['score'], 1)}: {counted}. "
            f"Giriş {num(r['entry'])}, stop {num(r['stop'])} (%{num(r['stopPercent'])}). {_exit(r)}{result} En iyi {signed(r['maxProfit']['percent'])}% (teminata göre %{num(r['maxProfit']['roiPercent'], 1)}), "
            f"en kötü {signed(r['maxLoss']['percent'])}%. Toplam {sum(len(v) for v in r['confirmations'].values())} onay bulunmuştu.")


def standard(r: dict) -> str:
    why = ", ".join(PLAIN.get(c, "bir teknik kural dönüşü destekledi") for c in r["categories"])
    side = "yükseleceği" if r["direction"] == "LONG" else "düşeceği"
    if r["status"] != "CLOSED":
        end = f"İşlem sürüyor. Şu ana kadar kasaya etkisi {signed(r['pnlUsd'])} $."
    elif r["pnlUsd"] > 0:
        end = f"İşlem {signed(r['pnlUsd'])} $ kazançla kapandı."
    else:
        end = f"İşlem {signed(r['pnlUsd'])} $ zararla kapandı; kayıp baştan belirlenen stop sayesinde sınırlı kaldı." if r["exitReason"] == "STOP" else f"İşlem {signed(r['pnlUsd'])} $ ile kapandı."
    return (f"Sistem {r['openedAtTsi']} (TSİ) itibarıyla {r['asset']} fiyatının {side} yönünde sanal bir işlem açtı. Nedenleri: {why}. "
            f"Kasadan {num(r['marginUsd'])} $ kullanıldı. {_exit(r)} {end} Bu bir sanal işlemdir, yatırım tavsiyesi değildir; yöntemin kazandırdığına dair yeterli kanıt yok.")
