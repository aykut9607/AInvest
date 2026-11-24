"""Builds evaluation/report.html from the measurement files in evaluation/out (no network, no model calls).

    python evaluation/build_report.py

Re-run it after any evaluation script: every table is read from the JSON files, so a new configuration (for example
a LoRA model measured with --tag lora) shows up as a new row without touching this file. The page is self-contained
(inline CSS, no scripts) and opens offline.
"""

import html
import json
import re
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
REPORT = HERE / "report.html"

PRICES = {"claude-opus-5-5": (4.0, 20.0)}  # USD per million tokens (input, output)
# measured on scoring v1 (2026-11-21) before the results file was rewritten for v2; kept for the comparison
V1_MONOTONICITY = {"checked": 1200, "scoreDropped": 18}

MODEL_LABELS = {
    "gemma3:4b": "Gemma 3 4B", "llama3.1:8b": "Llama 3.1 8B", "mistral:7b": "Mistral 7B",
    "qwen2.5:14b": "Qwen 2.5 14B", "claude-opus-5-5": "Claude Opus 5.5 (referans)",
}
TAG_LABELS = {"base": "örneksiz istem, 3 tur", "fewshot": "örnekli istem, 3 tur"}
REASON_TR = {
    "UNVERIFIED_NUMBERS": "veride olmayan sayı", "WRONG_LANGUAGE": "başka alfabe", "EMPTY_OUTPUT": "boş cevap",
    "LLM_UNAVAILABLE": "model çalışmadı", "BLOCKED_INPUT": "saldırı engellendi", "UNSUPPORTED": "desteklenmeyen konu",
    "NO_DATA": "veri yok", "NO_BREAKDOWN": "döküm yok", "DATA_UNAVAILABLE": "veriye ulaşılamadı",
}


# --- formatting -------------------------------------------------------------------------------------------------------
def esc(value) -> str:
    return html.escape(str(value), quote=True)


def num(value: float, decimals: int = 0) -> str:
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "\0").replace(".", ",").replace("\0", ".")


def pct(rate: float | None, decimals: int = 1) -> str:
    if rate is None:
        return "–"
    text = num(rate * 100, decimals)
    return "%" + (text[:-2] if text.endswith(",0") else text)


def usd(tokens: dict | None, model: str = "claude-opus-5-5") -> float:
    if not tokens:
        return 0.0
    price_in, price_out = PRICES[model]
    return tokens["input_tokens"] * price_in / 1e6 + tokens["output_tokens"] * price_out / 1e6


def label(config: str) -> str:
    """'router:gemma3:4b+fewshot' -> 'router · Gemma 3 4B (örnekli istem, 3 tur)'."""
    config, _, tag = config.partition("+")
    mode = ""
    if config.startswith(("router:", "tools:")):
        mode, config = config.split(":", 1)
    text = MODEL_LABELS.get(config, config)
    if tag:
        text += f" ({TAG_LABELS.get(tag, tag)})"
    return f"{mode} · {text}" if mode else text


def bar(rate: float | None, good_high: bool = True) -> str:
    """A percentage cell with a thin single-hue bar (magnitude); the number is always written next to it."""
    if rate is None:
        return '<td class="n">–</td>'
    width = max(0.0, min(1.0, rate)) * 100
    tip = f"{pct(rate)} ({'yüksek daha iyi' if good_high else 'düşük daha iyi'})"
    return (f'<td class="n" title="{esc(tip)}"><span class="v">{pct(rate)}</span>'
            f'<span class="track"><span class="fill" style="width:{width:.1f}%"></span></span></td>')


def table(head: list[str], rows: list[str], caption: str = "") -> str:
    cap = f"<caption>{caption}</caption>" if caption else ""
    return (f'<div class="scroll"><table>{cap}<thead><tr>{"".join(f"<th>{h}</th>" for h in head)}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')


def load(name: str) -> dict:
    path = OUT / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


# --- sections ---------------------------------------------------------------------------------------------------------
def tiles(results: dict, coach: dict, assistant: dict, coach_v1: dict, realism: dict) -> str:
    mono = results.get("a_monotonicity", {})
    repro = results.get("a_reproducibility", {})
    best = assistant.get("router:gemma3:4b+fewshot") or assistant.get("router:gemma3:4b") or {}
    configs = {k: v for k, v in assistant.items() if k != "parameters"}
    blocked = all(v.get("attacksBlocked") == 1.0 for v in configs.values())
    spent = sum(usd(v.get("tokens")) for d in (coach, assistant, coach_v1) for k, v in d.items() if k != "parameters")
    items = [
        (f"{num(mono.get('scoreDropped', 0))} / {num(mono.get('checked', 0))}",
         "olumlu değişiklikte skor düştü (IQ v2)",
         f"v1: {num(V1_MONOTONICITY['scoreDropped'])} / {num(V1_MONOTONICITY['checked'])}"),
        (f"{num(repro.get('identical', 0))} / {num(repro.get('profiles', 0))}", "aynı girdi, aynı skor",
         "kural tabanlı skor tekrar üretilebilir"),
        (pct(best.get("correct")), "asistan doğru değeri verdi", f"Gemma 3 4B, router, {best.get('questions', 0)} soru"),
        ("hepsinde" if blocked else "eksik", "istem saldırıları engellendi", f"{len(configs)} yapılandırma"),
        (f"${num(spent, 2)}", "Claude referans ölçümlerinin toplamı", "üründe kullanılmıyor"),
    ]
    reserve = next((r for r in realism.get("rows", []) if r["key"] == "lastsOver2MonthsCash"), None)
    if reserve and reserve["synthetic"] is not None:
        items.append((f"{pct(reserve['synthetic'])} / {pct(reserve['turkey'])}",
                      "gelir kesilse 2 aydan uzun idare edebilir (sentetik / Türkiye)",
                      "sentetik nüfus fazla iyimser" if reserve["synthetic"] > reserve["turkey"] + 0.05
                      else "Findex 2025 ile karşılaştırma"))
    return '<div class="tiles">' + "".join(
        f'<div class="tile"><div class="big">{esc(a)}</div><div>{esc(b)}</div><div class="hint">{esc(c)}</div></div>'
        for a, b, c in items) + "</div>"


def pipeline() -> str:
    steps = [
        ("Profil", "kullanıcının girdiği tutarlar"),
        ("Financial IQ", "C# kuralları: skor, 5 faktör, uyarılar"),
        ("Veri bloğu", "Python kodu oranları ve tutarları hesaplar"),
        ("Model", "yerel (Ollama) model yalnızca cümle kurar"),
        ("Denetim", "boş mu, Türkçe mi, her sayı veride var mı"),
        ("Kullanıcı", "geçerse modelin cevabı, geçmezse şablon"),
    ]
    return '<ol class="flow">' + "".join(f"<li><b>{esc(a)}</b><span>{esc(b)}</span></li>" for a, b in steps) + "</ol>"


def iq_section(results: dict) -> str:
    if not results:
        return "<p>out/results.json yok: <code>run_evaluation.py</code> çalıştırılmamış.</p>"
    p = results["parameters"]
    counts = results["archetypeVsSegment"]
    rows = []
    expected = {"strong": "HIGH", "average": "MEDIUM", "fragile": "LOW"}
    names = {"strong": "Güçlü", "average": "Ortalama", "fragile": "Kırılgan"}
    for archetype in ("strong", "average", "fragile"):
        total = sum(v for k, v in counts.items() if k.startswith(archetype + "->"))
        cells = []
        for segment in ("LOW", "MEDIUM", "HIGH"):
            n = counts.get(f"{archetype}->{segment}", 0)
            mark = ' class="hit"' if segment == expected[archetype] else ""
            cells.append(f'<td class="n"{mark}>{n} <span class="hint">({pct(n / total if total else 0, 0)})</span></td>')
        rows.append(f"<tr><th>{names[archetype]}</th>{''.join(cells)}</tr>")
    archetypes = table(["Sentetik profil tipi", "LOW", "MEDIUM", "HIGH"], rows,
                       "Beklenen segment çerçeveli. Ortalama tipin bir bölümü HIGH çıkıyor; ortalama ile güçlü "
                       "arasındaki sınır, segment eşikleriyle birlikte IQ kural tablosunda gözden geçirilecek.")

    mono = results["a_monotonicity"]
    mono_rows = [f"<tr><th>{esc(change)}</th><td class='n'>{num(v['checked'])}</td>"
                 f"<td class='n'>{num(v.get('scoreDropped', 0))}</td></tr>" for change, v in mono["perChange"].items()]
    monotonicity = table(["Olumlu değişiklik", "Denenen", "Skor düştü"], mono_rows)

    dirty = results["b_dirtyData"]
    d_rows = []
    for key, name in (("naiveRepair", "Basit onarım"), ("reportCleaning", "Rapordaki temizleme")):
        for scope, scope_name in (("corruptedOnly", "bozulan kayıtlar"), ("all", "tüm kayıtlar")):
            s = dirty[key][scope]
            d_rows.append(f"<tr><th>{name}, {scope_name} ({s['records']})</th>{bar(s['sameSegmentRate'])}"
                          f"<td class='n'>{num(s['meanAbsScoreDiff'], 1)}</td><td class='n'>{s['maxAbsScoreDiff']}</td></tr>")
    kinds = {"missing values": "eksik değer", "erroneous records": "hatalı kayıt"}
    corruption = ", ".join(f"{v} {kinds.get(k, k)}" for k, v in dirty["corruption"].items())
    dirty_table = table(["Yöntem", "Segment aynı kaldı", "Ort. skor farkı", "En büyük fark"], d_rows,
                        f"Bozulma: {esc(corruption)} ({pct(p['missing_rate'])} eksik, {pct(p['error_rate'])} hatalı).")

    return f"""
<p>{num(p['n'])} sentetik profil (tohum {p['seed']}), üründeki C# kurallarıyla (<code>FinancialIQ.BatchScorer</code>)
puanlandı. Puanlama sürümü: {esc(', '.join(f'{k}: {v}' for k, v in results['scoringVersion'].items()))}.</p>
<h3>Segment ayrımı</h3>{archetypes}
<h3>Monotonluk: daha iyi veri skoru düşürmemeli</h3>
<p>Her profilde altı olumlu değişiklik tek tek denendi. v2'de <b>{num(mono['scoreDropped'])} / {num(mono['checked'])}</b>
durumda skor düştü; v1'de bu sayı {V1_MONOTONICITY['scoreDropped']} / {num(V1_MONOTONICITY['checked'])} idi (v1'deki
risk uyumu faktörü yüzünden; v2'de bu faktör kaldırıldı).</p>{monotonicity}
<h3>Kirli veri</h3>
<p>Kayıtların bir kısmı bozuldu, sonra iki yolla onarıldı. Bozulan kayıtlarda iki yöntemin ortalama farkı benzer, ama
rapordaki temizleme en kötü durumda daha çok sapıyor. Sonuç: hatalı görünen bir kaydı sessizce düzeltmek yerine
kullanıcıya sormak daha güvenli.</p>{dirty_table}"""


def realism_section(realism: dict) -> str:
    """The synthetic population next to published Turkish shares (out/realism_clean.json from realism_check.py)."""
    if not realism:
        return "<p>out/realism_clean.json yok: <code>realism_check.py</code> çalıştırılmamış.</p>"
    rows = {r["key"]: r for r in realism["rows"]}
    extras = realism.get("extras", {})

    def pair(key: str) -> tuple[float | None, float | None]:
        r = rows.get(key)
        return (r["synthetic"], r["turkey"]) if r and r["synthetic"] is not None else (None, None)

    def value(r: dict, v: float | None) -> str:
        if v is None:
            return "–"
        if r["unit"] == "share":
            return pct(v)
        return f"{num(v)} TL" if r["unit"] == "tl" else f"{num(v, 1)} kat"

    def difference(r: dict) -> str:
        s, t = r["synthetic"], r["turkey"]
        if s is None or r["unit"] == "ratio":
            return "–"
        if r["unit"] == "tl":
            return f"{num(s / t, 1)} kat"
        d = (s - t) * 100
        return f"{'+' if d >= 0 else '−'}{num(abs(d), 1)} puan"

    def axis(r: dict) -> str:
        # dumbbell on a 0-100% scale: the synthetic share is a filled accent circle, Türkiye a hollow ink diamond
        # drawn on top, so both stay visible when the two values almost coincide
        if r["unit"] != "share" or r["synthetic"] is None:
            return "<td></td>"
        s, t = (max(0.0, min(1.0, x)) * 100 for x in (r["synthetic"], r["turkey"]))
        tip = f"Türkiye {pct(r['turkey'])} · Sentetik {pct(r['synthetic'])}"
        return (f'<td title="{esc(tip)}"><span class="axis">'
                f'<span class="gap" style="left:{min(s, t):.1f}%;width:{abs(s - t):.1f}%"></span>'
                f'<span class="dot syn" style="left:{s:.1f}%"></span>'
                f'<span class="dot tr" style="left:{t:.1f}%"></span></span></td>')

    body = [f"<tr><th>{esc(r['label'])}</th><td class='n'>{value(r, r['turkey'])}</td>"
            f"<td class='n'>{value(r, r['synthetic'])}</td><td class='n'>{difference(r)}</td>{axis(r)}"
            f"<td class='wide'>{esc(r['proxy'])}<div class='hint'>{esc(r['fit'])} ölçü. {esc(r['note'])}</div></td>"
            f"<td class='wide'><a href='{esc(r['url'])}'>{esc(r['source'])}</a>"
            f"<div class='hint'>{esc(r['year'])} · {esc(r['sourceStatus'])}</div></td></tr>" for r in realism["rows"]]

    def lean(s: float, t: float, high: str, low: str, near: str) -> str:
        return high if s > t + 0.05 else low if s < t - 0.05 else near

    points = []
    cash, t_cash = pair("lastsOver2MonthsCash")
    cover, t_cover = pair("cannotCoverUnexpected")
    if cash is not None and cover is not None:
        text = (f"<b>{lean(cash, t_cash, 'Sentetik nüfus rezervde fazla iyimser.', 'Sentetik nüfus rezervde fazla kötümser.', 'Rezerv payı Türkiye’ye yakın.')}</b> "
                f"Gelir kesilirse 2 aydan uzun idare edebilenler Türkiye'de {pct(t_cash)}, sentetik nüfusta yalnız nakitle "
                f"{pct(cash)}. Beklenmedik bir harcamayı karşılayamayanlar Türkiye'de {pct(t_cover)}, sentetik nüfusta "
                f"{pct(cover)}")
        text += " (ölçü sentetik payı olduğundan yüksek gösterdiği halde)." if cover < t_cover else "."
        points.append(text)
    inst, t_inst = pair("hasInstallment")
    debt, t_debt = pair("debtPerDebtor")
    if inst is not None:
        text = (f"<b>{lean(inst, t_inst, 'Borç fazla yaygın.', 'Borç az yaygın.', 'Borç yaygınlığı Türkiye’ye yakın.')}</b> "
                f"Taksidi olanlar Türkiye'de {pct(t_inst)}, sentetik nüfusta {pct(inst)}.")
        if debt is not None:
            text += (f" Borçlu başına ortalama borç sentetik nüfusta {num(debt)} TL, Türkiye'de kredi kullanan kişi "
                     f"başına {num(t_debt)} TL ({num(debt / t_debt, 1)} kat).")
        points.append(text)
    saved, t_saved = pair("saved")
    if saved is not None:
        points.append(f"<b>{lean(saved, t_saved, 'Tasarruf eden payı yüksek.', 'Tasarruf eden payı düşük.', 'Tasarruf eden payı yakın.')}</b> "
                      f"Son yılda tasarruf edenler Türkiye'de {pct(t_saved)}, sentetik nüfusta aylık artısı olanlar "
                      f"{pct(saved)} (kaba ölçü).")
    top, t_top = pair("incomeTop20")
    grad, t_grad = pair("incomeGradient")
    if top is not None:
        text = (f"<b>{lean(top, t_top, 'Gelir fazla eşitsiz dağılmış.', 'Gelir fazla eşit dağılmış.', 'Gelir dağılımı Türkiye’ye yakın.')}</b> "
                f"Gelirin en üst %20'ye düşen payı Türkiye'de {pct(t_top)}, sentetik nüfusta {pct(top)}.")
        if grad is not None and grad < 1.5 <= t_grad:
            text += (f" Türkiye'de düşük gelirliler beklenmedik harcamayı {num(t_grad, 1)} kat daha sık karşılayamıyor; "
                     f"sentetik nüfusta bu ilişki yok ({num(grad, 1)} kat), çünkü üretici geliri profil tipinden bağımsız seçiyor.")
        points.append(text)

    order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}
    segments = ", ".join(f"{k} {pct(v)}" for k, v in sorted(extras.get("segments", {}).items(),
                                                             key=lambda kv: order.get(kv[0], 9)))
    gaps = [abs(s - t) for s, t in (pair("lastsOver2MonthsCash"), pair("cannotCoverUnexpected"),
                                    pair("hasInstallment")) if s is not None]
    representative = bool(gaps) and max(gaps) <= 0.10
    validity = (f"<p><b>Ne geçerli, ne değil.</b> Monotonluk ve tekrar üretilebilirlik sonuçları nüfusun "
                f"gerçekçiliğine bağlı değil, geçerliliklerini koruyor. Segment dağılımı ({segments}) ve rezerv "
                f"faktöründen en az 15 puan alanların payı ({pct(extras.get('reservePointsAtLeast15'))}) ise bu nüfusa "
                f"bağlı ve " + ("Türkiye paylarına yakın bir nüfustan geliyor." if representative else
                                "Türkiye'yi temsil etmiyor."))
    if cash is not None and cash > t_cash + 0.05:
        validity += " Türkiye'ye benzeyen bir nüfusta LOW payının daha yüksek çıkması beklenir; bu henüz ölçülmedi."
    validity += "</p>"

    legend = ('<div class="legend"><span class="key"><span class="tr"></span>Türkiye</span>'
              '<span class="key"><span class="syn"></span>Sentetik nüfus</span>'
              '<span>ölçek %0–100, yalnız pay satırlarında</span></div>')
    head = ["Gösterge", "Türkiye", "Sentetik", "Fark", "Ölçek", "Sentetik nüfustaki ölçü", "Kaynak"]
    return f"""
<p>Danışmanın notu: tamamen sentetik veri yerine gerçekçi veri. Türkiye'de skorun 7 girdisini aynı kişide tutar olarak
veren açık bir veri seti yok. Bu yüzden IQ değerlendirmesindeki {num(realism.get('profiles', 0))} sentetik profilin,
yayımlanmış Türkiye paylarını (Global Findex 2025, TÜİK GYKA / Eurostat, TBB Risk Merkezi) tutup tutmadığına bakıldı.
Anket sorusu ile skorun oranı hiçbir zaman birebir aynı değil; her satır ölçünün ne kadar yakın olduğunu ve hangi yöne
yanıldığını yazıyor. Betik: <code>evaluation/realism_check.py</code>.</p>
<ul>{''.join(f'<li>{p}</li>' for p in points)}</ul>
{legend}
{table(head, body, "Fark: sentetik eksi Türkiye (yüzde puanı) ya da oran. “Yakın” ölçü anket sorusuna doğrudan "
       "karşılık geliyor, “kaba” ölçü yalnızca yönü gösteriyor. “İkincil” kaynaklar haber ya da derleme sitesi; "
       "TÜİK bülteninden teyit edilecek.")}
{validity}
<p><b>Sonraki adımlar.</b> (1) Türkiye paylarına göre ayarlanmış bir sentetik nüfus: gelir TÜİK dağılımına, rezerv
Findex'e, taksit oranı GYKA'ya göre, kırılganlık gelire bağlı; aynı kurallarla puanlanıp segment dağılımı yeniden
ölçülecek. (2) TÜİK GYKA mikroverisiyle dış geçerlik: beklenmedik harcamayı karşılayamadığını söyleyenler gerçekten
düşük skor alıyor mu? (3) Findex rakamları PDF metninden çıkarıldı, s. 147'de gözle teyit edilecek.</p>"""


def coach_section(coach: dict, coach_v1: dict) -> str:
    def rows(data: dict) -> list[str]:
        out = []
        for name, m in data.items():
            if name == "parameters":
                continue
            o = m["of_model_answers"]
            reasons = ", ".join(f"{REASON_TR.get(k, k)}: {v}" for k, v in m.get("fallback_reasons", {}).items()) or "–"
            cost = f"${num(usd(m.get('tokens')), 2)}" if m.get("tokens") else "yerel"
            out.append(f"<tr><th>{esc(label(name))}</th>{bar(m['fallback_rate'], False)}<td>{esc(reasons)}</td>"
                       f"{bar(o['siz_used'], False)}{bar(o['over_6_sentences'], False)}{bar(o['multi_paragraph'], False)}"
                       f"<td class='n'>{num(m['seconds_mean'], 1)} sn</td><td class='n'>{num(m['seconds_p90'], 1)} sn</td>"
                       f"<td class='n'>{cost}</td></tr>")
        return out

    head = ["Model", "Şablona düştü", "Neden", "“siz” hitabı", "6 cümleyi aştı", "Birden çok paragraf", "Ort. süre",
            "p90", "Maliyet"]
    p = coach.get("parameters", {})
    v1 = ""
    if coach_v1:
        v1 = (f"<details><summary>Scoring v1 ölçümü (Qwen 2.5 14B dahil)</summary>"
              f"{table(head, rows(coach_v1), 'Qwen bir cevabı Çince yazdı; sayı denetimi bunu yakalayamadığı için dil denetimi eklendi. Ortalama 33 sn ile demoda kullanılamayacak kadar yavaş.')}</details>")
    return f"""
<p>Her segmentten {p.get('per_segment', '?')} profil, toplam {3 * p.get('per_segment', 0)} açıklama (scoring
{esc(p.get('scoring', '?'))}). Oranlar modelin kendi cevaplarına göre; şablona düşen cevaplar oranlara katılmaz.
<b>Ölçüm, 6 cümle sınırı koda eklenmeden önce yapıldı.</b> Artık 6 cümleyi aşan cevap kodla kısaltılıyor (ilk cümleler
ve öneriyi taşıyan son cümle kalıyor), bu yüzden bu sütun bugün kullanıcıya yansımıyor.</p>
{table(head, rows(coach))}
<p class="hint">Gemma'nın 6 cümleyi aşma oranı turdan tura %7 ile %17 arasında oynuyor; 30 cevaplık tek tur bu fark için
gürültülü.</p>{v1}"""


def assistant_section(assistant: dict) -> str:
    rows = []
    for name, m in assistant.items():
        if name == "parameters":
            continue
        reasons = ", ".join(f"{REASON_TR.get(k, k)}: {v}" for k, v in sorted(m.get("fallbacks", {}).items())) or "–"
        cost = f"${num(usd(m.get('tokens')), 2)}" if m.get("tokens") else "yerel"
        rows.append(f"<tr><th>{esc(label(name))}</th><td class='n'>{m['questions']}</td>{bar(m['routed'])}"
                    f"{bar(m['correct'])}{bar(m['modelAnswered'])}{bar(m['declined'])}{bar(m['attacksBlocked'])}"
                    f"{bar(m['sizInModelAnswers'], False)}<td class='wide'>{esc(reasons)}</td>"
                    f"<td class='n'>{num(m['secondsMean'], 1)} sn</td><td class='n'>{cost}</td></tr>")
    head = ["Yapılandırma", "Soru", "Doğru veri", "Doğru değer", "Model cevapladı", "Desteklenmeyeni reddetti",
            "Saldırı engellendi", "“siz” hitabı", "Şablon nedenleri", "Ort. süre", "Maliyet"]
    scores = assistant.get("parameters", {}).get("scores", {})
    return f"""
<p>28 soru: veri soruları (borç, yatırım, nakit, skor, geçmiş, uyarı, portföy), SSS, desteklenmeyenler (BTC fiyatı,
kur, hava durumu), profili olmayan kullanıcı ve 3 istem saldırısı. İki demo kullanıcı (skorları
{esc(', '.join(f'{k} {v}' for k, v in scores.items()))}), veriler kodla hesaplandı.</p>
<ul>
<li><b>router</b>: model yalnızca kapalı bir listeden hangi verinin gerektiğini seçer; veriyi kod getirir ve hesaplar,
model cümleye çevirir. Gemma'da araç çağırma olmadığı için üründe bu mod kullanılıyor.</li>
<li><b>tools</b>: model aracı kendisi çağırır. Araçlar yine kodun hesapladığı satırları döndürür.</li>
</ul>
{table(head, rows)}
<p class="hint">“Doğru değer”, cevabı model de şablon da yazsa beklenen tutarın cevapta geçip geçmediğidir: kullanıcıya
yanlış sayı gitmiyor. “Model cevapladı” oranındaki farkın çoğu tasarım gereği: router modunda desteklenmeyen sorular ve
saldırılar modele hiç gönderilmiyor.</p>"""


def fewshot_section(coach: dict, assistant: dict) -> str:
    a0, a1 = assistant.get("router:gemma3:4b+base"), assistant.get("router:gemma3:4b+fewshot")
    c0, c1 = coach.get("gemma3:4b+base"), coach.get("gemma3:4b+fewshot")
    if not (a0 and a1):
        return "<p>Örnekli istem ölçümü yok.</p>"

    def answered(m):
        skipped = sum(m["fallbacks"].get(k, 0) for k in ("BLOCKED_INPUT", "UNSUPPORTED", "NO_DATA"))
        return m["questions"] - skipped

    def unverified(m):
        return m["fallbacks"].get("UNVERIFIED_NUMBERS", 0)

    rows = [
        ("Asistan: veride olmayan sayı yazıp reddedildi",
         f"{unverified(a0)} / {answered(a0)} ({pct(unverified(a0) / answered(a0))})",
         f"{unverified(a1)} / {answered(a1)} ({pct(unverified(a1) / answered(a1))})"),
        ("Asistan: doğru değer", pct(a0["correct"]), pct(a1["correct"])),
        ("Asistan: “siz” hitabı", pct(a0["sizInModelAnswers"]), pct(a1["sizInModelAnswers"])),
    ]
    if c0 and c1:
        rows.append(("Koç: 6 cümleyi aştı (kısaltma öncesi)", pct(c0["of_model_answers"]["over_6_sentences"]),
                     pct(c1["of_model_answers"]["over_6_sentences"])))
    body = [f"<tr><th>{esc(a)}</th><td class='n'>{esc(b)}</td><td class='n'>{esc(c)}</td></tr>" for a, b, c in rows]
    return f"""
<p>İsteme uydurma sayılarla yazılmış örnek cevaplar eklendi (<code>PROMPT_EXAMPLES</code>). Örnekteki bir sayı
kopyalanırsa sayı denetimi bunu yakalar, çünkü o sayı kullanıcının verisinde yok. Aynı soru seti Gemma 3 4B ile
üçer kez çalıştırıldı.</p>
{table(["Ölçüm", "Örneksiz", "Örnekli"], body)}
<p>Koç cevaplarının uzunluğunu örnekler değiştirmedi; bu yüzden uzunluk sınırı koda kondu.</p>"""


def lora_section(assistant: dict) -> str:
    a1 = assistant.get("router:gemma3:4b+fewshot")
    rest = ""
    if a1:
        skipped = sum(a1["fallbacks"].get(k, 0) for k in ("BLOCKED_INPUT", "UNSUPPORTED", "NO_DATA"))
        n = a1["questions"] - skipped
        rest = f" Kalan sorun, Gemma'nın cevapların {pct(a1['fallbacks'].get('UNVERIFIED_NUMBERS', 0) / n)}'inde kendi hesabını yapmaya kalkması."
    lora_rows = [k for k in assistant if "lora" in k.lower()]
    status = ("LoRA ölçümü tablolarda." if lora_rows else
              "Henüz LoRA ölçümü yok. Eğitilen model <code>ollama create</code> ile eklenip aynı betiklerle "
              "<code>--tag lora</code> ölçüldüğünde, bu sayfayı yeniden üretmek onu tablolara satır olarak ekler; "
              "canlı deneme sayfasında da model listesinde kendiliğinden görünür.")
    return f"""
<p><b>Karar (22 Kasım): LoRA şimdilik yapılmıyor.</b> Örnekli istem ve kod denetimleriyle kullanıcıya hiç yanlış sayı
gitmiyor.{rest} Sayı denetimi bunu yakalıyor; kullanıcı doğru ama daha kuru olan şablon cevabı görüyor. LoRA'nın
getirebileceği kazanç bu oran. Makine yeterli (RTX 3070 Laptop 8 GB, Gemma 3 4B QLoRA sınırda sığıyor); zaman kalırsa
Faz 8'de aynı ölçümle önce/sonra karşılaştırılarak yapılacak.</p>
<p>{status}</p>"""


def cost_section(coach: dict, assistant: dict, coach_v1: dict) -> str:
    rows, total = [], 0.0
    for title, data in (("Koç, scoring v2", coach), ("Asistan", assistant), ("Koç, scoring v1", coach_v1)):
        for name, m in data.items():
            if name != "parameters" and m.get("tokens"):
                cost = usd(m["tokens"])
                total += cost
                rows.append(f"<tr><th>{esc(title)}: {esc(label(name))}</th><td class='n'>{num(m['tokens']['input_tokens'])}</td>"
                            f"<td class='n'>{num(m['tokens']['output_tokens'])}</td><td class='n'>${num(cost, 2)}</td></tr>")
    rows.append(f"<tr class='sum'><th>Toplam</th><td></td><td></td><td class='n'>${num(total, 2)}</td></tr>")
    price_in, price_out = PRICES["claude-opus-5-5"]
    return f"""
<p>Claude Opus 5.5 yalnızca değerlendirmede, yerel modellerin üst referansı olarak kullanıldı. Ona giden tek şey
sentetik profillerden üretilen veri bloklarıydı. Üründe model yerel (Ollama) kalıyor: gizlilik ve maliyet kararı.
Fiyat: 1 milyon girdi tokeni ${num(price_in)}, 1 milyon çıktı tokeni ${num(price_out)}.</p>
{table(["Ölçüm", "Girdi token", "Çıktı token", "Maliyet"], rows)}"""


def limits_section() -> str:
    return """
<ul>
<li><b>Veri sentetik.</b> Profiller kural tabanlı bir üreticiden geliyor; yayımlanmış Türkiye paylarıyla
karşılaştırması <a href="#gercek">ayrı bölümde</a>. Önceki tezlerle karşılaştırma YÖK araştırmasının konusu (danışman
notu 3).</li>
<li><b>Sayı denetimi yanlış eşleştirmeyi yakalamaz.</b> Bir sayı verinin başka bir yerinde geçiyorsa, yanlış şeye
atfedilse de denetimden geçer. Örnek: tools + Llama “fonun 3 ay yeter” dedi (doğrusu 0,3 ay); 3 sayısı veride başka bir
satırda vardı. Yazıyla yazılmış sayılar (“on iki bin”) da yakalanmaz; istemler rakam istiyor.</li>
<li><b>Tek tur gürültülü.</b> Modeller örnekleme yapıyor (sıcaklık 0,2); küçük farklar için soru seti üç kez çalıştırıldı.</li>
<li><b>Denetimin yakaladığı gerçek hatalar</b> (Gemma, asistan): “12.000 TL gelir”, “18,5 aylık”, “7.200”. Hepsi
reddedildi, kullanıcı şablonu gördü.</li>
</ul>"""


def outputs_section() -> str:
    parts = []
    for file, title in (("model_outputs.md", "Koç açıklamaları (scoring v2)"), ("assistant_outputs.md", "Asistan cevapları")):
        path = OUT / file
        if not path.exists():
            continue
        chunks = path.read_text(encoding="utf-8").split("\n## ")[1:]
        inner = []
        for chunk in chunks:
            name, _, body = chunk.partition("\n")
            items = []
            for block in re.split(r"\n(?=\*\*)", body.strip()):
                head, _, text = block.partition("\n")
                head = esc(head).replace("**", "")
                items.append(f"<div class='out'><div class='hint'>{head}</div><p>{esc(text.strip())}</p></div>")
            inner.append(f"<details><summary>{esc(label(name.strip()))} ({len(items)})</summary>{''.join(items)}</details>")
        parts.append(f"<h3>{esc(title)}</h3>{''.join(inner)}")
    return "".join(parts) or "<p>Çıktı dosyası yok.</p>"


STYLE = """
:root { --page:#f9f9f7; --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --muted:#898781; --line:#e1e0d9;
  --accent:#2a78d6; --track:#ecebe6; --code:#f2f1ed; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --page:#0d0d0d; --surface:#1a1a19;
  --ink:#f0efec; --ink-2:#c3c2b7; --line:#2c2c2a; --accent:#3987e5; --track:#2c2c2a; --code:#262624; } }
:root[data-theme="dark"] { --page:#0d0d0d; --surface:#1a1a19; --ink:#f0efec; --ink-2:#c3c2b7; --line:#2c2c2a;
  --accent:#3987e5; --track:#2c2c2a; --code:#262624; }
* { box-sizing:border-box; }
body { margin:0; background:var(--page); color:var(--ink); font:15px/1.6 system-ui,-apple-system,"Segoe UI",sans-serif; }
main { max-width:1180px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:26px; margin:0 0 4px; } h2 { font-size:20px; margin:36px 0 8px; padding-top:12px; border-top:1px solid var(--line); }
h3 { font-size:16px; margin:20px 0 6px; }
.hint { color:var(--muted); font-size:13px; }
code { background:var(--code); padding:1px 5px; border-radius:4px; font-size:13px; overflow-wrap:anywhere; }
nav { display:flex; flex-wrap:wrap; gap:6px 14px; font-size:14px; margin:14px 0; } nav a { color:var(--accent); }
.tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr)); gap:10px; margin:18px 0; }
.tile { background:var(--surface); border:1px solid var(--line); border-radius:10px; padding:12px 14px; font-size:14px; }
.tile .big { font-size:28px; font-weight:700; font-variant-numeric:tabular-nums; line-height:1.2; }
.flow { list-style:none; padding:0; display:grid; grid-template-columns:repeat(auto-fit,minmax(150px,1fr)); gap:8px; counter-reset:s; }
.flow li { background:var(--surface); border:1px solid var(--line); border-radius:8px; padding:10px; font-size:13px; display:flex; flex-direction:column; counter-increment:s; }
.flow li b::before { content:counter(s) ". "; color:var(--muted); }
.flow li span { color:var(--ink-2); }
.scroll { overflow-x:auto; margin:8px 0; }
table { border-collapse:collapse; width:100%; font-size:13.5px; background:var(--surface); }
caption { caption-side:bottom; text-align:left; color:var(--muted); font-size:12.5px; padding-top:6px; }
th, td { padding:6px 8px; border-bottom:1px solid var(--line); text-align:left; vertical-align:top; }
thead th { font-size:12px; color:var(--ink-2); font-weight:600; }
tbody th { font-weight:500; }
td.n { text-align:right; font-variant-numeric:tabular-nums; white-space:nowrap; }
td.hit { box-shadow:inset 0 0 0 2px var(--accent); font-weight:600; }
td.wide { min-width:230px; }
.v { display:inline-block; min-width:44px; }
.track { display:inline-block; width:60px; height:6px; background:var(--track); border-radius:3px; margin-left:6px; vertical-align:middle; overflow:hidden; }
.fill { display:block; height:100%; background:var(--accent); border-radius:3px; }
tr.sum th, tr.sum td { font-weight:700; }
details { margin:6px 0; } summary { cursor:pointer; color:var(--ink-2); }
.out { border-top:1px solid var(--line); padding:6px 0; } .out p { margin:2px 0; white-space:pre-wrap; }
a { color:var(--accent); }
.legend { display:flex; flex-wrap:wrap; gap:4px 16px; font-size:13px; color:var(--ink-2); margin:10px 0 4px; }
.key { display:inline-flex; align-items:center; gap:6px; }
.key span, .axis .dot { display:inline-block; width:10px; height:10px; }
.axis { position:relative; display:inline-block; width:150px; height:14px; vertical-align:middle; }
.axis::before { content:""; position:absolute; left:0; right:0; top:6px; height:2px; background:var(--track); border-radius:1px; }
.axis .gap { position:absolute; top:6px; height:2px; background:var(--muted); }
.axis .dot { position:absolute; top:2px; margin-left:-5px; box-shadow:0 0 0 2px var(--surface); }
.tr { background:transparent; border:2px solid var(--ink); border-radius:1px; transform:rotate(45deg); }
.axis .dot.tr { box-shadow:none; }
.syn { background:var(--accent); border-radius:50%; }
"""


def build() -> str:
    results, coach, assistant = load("results.json"), load("model_comparison.json"), load("assistant_comparison.json")
    coach_v1, realism = load("model_comparison_v1.json"), load("realism_clean.json")
    sections = [
        ("nasil", "Nasıl çalışıyor", pipeline() + "<p>Altın kural: oranları ve tutarları kod hesaplar; model yalnızca "
         "açıklar ve kendi sayısını yazamaz. Bunu her cevapta kod denetliyor.</p>"),
        ("iq", "Financial IQ kuralları (v2)", iq_section(results)),
        ("gercek", "Sentetik nüfus Türkiye verisine benziyor mu?", realism_section(realism)),
        ("koc", "Koç: skor açıklaması, model karşılaştırması", coach_section(coach, coach_v1)),
        ("asistan", "Asistan: router ve tools, model karşılaştırması", assistant_section(assistant)),
        ("ornek", "İsteme örnek cevap eklemek", fewshot_section(coach, assistant)),
        ("lora", "LoRA", lora_section(assistant)),
        ("maliyet", "Claude referansı: maliyet ve gizlilik", cost_section(coach, assistant, coach_v1)),
        ("sinir", "Sınırlar", limits_section()),
        ("cikti", "Ham çıktılar", outputs_section()),
    ]
    nav = "".join(f'<a href="#{k}">{esc(t)}</a>' for k, t, _ in sections)
    body = "".join(f'<h2 id="{k}">{esc(t)}</h2>{content}' for k, t, content in sections)
    return f"""<!doctype html>
<html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>AInvest AI Değerlendirmesi</title><style>{STYLE}</style></head>
<body><main>
<h1>AInvest AI katmanı: değerlendirme raporu</h1>
<div class="hint">Üretildi: {date.today().strftime('%d.%m.%Y')} · kaynak: <code>evaluation/out/*.json</code> ·
<code>python evaluation/build_report.py</code> ile yeniden üretilir, elle düzenlenmez. Canlı deneme:
<code>evaluation/playground.py</code>.</div>
{tiles(results, coach, assistant, coach_v1, realism)}
<nav>{nav}</nav>
{body}
</main></body></html>
"""


def main() -> None:
    REPORT.write_text(build(), encoding="utf-8")
    print(f"wrote {REPORT}")


if __name__ == "__main__":
    main()
