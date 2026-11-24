"""One page with every rule we have: its words and, where one exists, its picture.

  .\\venv\\Scripts\\python.exe -m signals.rules.rules_catalog        rebuild all-rules.html

The words come from the *.md rule lists and the pictures from the *-visuals.html pages next to them, so this page adds nothing of
its own. A picture is tied to a rule by the rule numbers written in it; pictures without a number are tied by LINKS below.
"""

from __future__ import annotations

import html
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

from signals.rules.chart import CHART_CSS
from signals.rules.elliott_draw import CSS

HERE = Path(__file__).parent
ID = r"[A-Z]{1,2}-(?:G\d+|\d+[a-z]?)"


@dataclass(frozen=True)
class Family:
    key: str
    name: str
    words: str                # rule list
    pictures: str | None      # visuals page


FAMILIES = [
    Family("elliott", "Elliott", "ELLIOTT.md", "elliott-visuals.html"),
    Family("harmonik", "Harmonik", "HARMONIC.md", "harmonic-visuals.html"),
    Family("fib", "Fibonacci", "FIBONACCI.md", "fib-visuals.html"),
    Family("pa", "Price action", "PRICE_ACTION.md", "pa-visuals.html"),
    Family("smc", "Smart money", "SMART_MONEY.md", "smc-visuals.html"),
    Family("pro", "Profesyonel", "PROFESSIONAL.md", "pro-visuals.html"),
    Family("mentor", "Mentor bakışı", "MENTOR_VIEW.md", "mentor-visuals.html"),
    Family("kitap", "Kitaplar", "BOOKS.md", "book-visuals.html"),
    Family("risk", "Risk ve davranış", "RISK.md", None),
]

# pictures that carry no rule number: (family, start of the title, how many earlier pictures share that start) -> rules
LINKS: dict[tuple[str, str], str] = {
    ("elliott", "Güdük 5"): "E-17", ("elliott", "3. dalganın içi"): "E-05 E-08",
    ("elliott", "Aynı dört nokta"): "E-93 E-91", ("elliott", "Geçersizlik dereceye"): "E-92",
    ("elliott", "Geçerli daralan diyagonal"): "E-20 E-25 E-26", ("elliott", "Geçerli zigzag"): "E-31 E-32 E-34",
    ("elliott", "B çok derin"): "E-33", ("elliott", "Normal yassı"): "E-40 E-41", ("elliott", "Genişleyen yassı"): "E-41 E-44",
    ("elliott", "Kaçan yassı"): "E-41 E-43", ("elliott", "Geçerli daralan üçgen"): "E-50 E-51 E-53",
    ("elliott", "W-X-Y (çift"): "E-60 E-61 E-62", ("elliott", "W-X-Y (zigzag"): "E-63", ("elliott", "B başlangıcı"): "E-55",
    ("elliott", "3. dalga hedefi"): "E-11 E-71", ("elliott", "5. dalga bölgesi"): "E-13 E-71 E-72", ("elliott", "Kanal"): "E-80 E-82",
    ("harmonik", "Düşen Bat"): "H-03 H-04", ("harmonik", "Gelişen Bat"): "H-12 H-20 H-21", ("harmonik", "Fiyat D"): "H-04 H-14 H-20",
    ("fib", "Trend fib (ana set)"): "FT-01 FT-02 FT-04", ("fib", "Trend fib (ikinci"): "FT-08", ("fib", "Fib retracement"): "FR-01 FR-02",
    ("fib", "Pazartesi aralığı"): "FM-01 FM-02 FM-03 FM-04 FM-05",
    ("pa", "Yükselişte BOS"): "PA-03 PA-04", ("pa", "BTCUSDT 1d: piyasa"): "PA-01 PA-02 PA-03 PA-04 PA-04a PA-06",
    ("pa", "GC 1d: piyasa"): "PA-01 PA-02 PA-03 PA-04 PA-04a", ("pa", "Aylık seviyeler"): "PA-20 PA-21",
    ("pa", "Trend çizgisi —"): "PA-10 PA-11 PA-12", ("pa", "Yükselen kama —"): "PA-30 PA-34 PA-39", ("pa", "Alçalan kama —"): "PA-31 PA-34 PA-39",
    ("pa", "Simetrik üçgen —"): "PA-32 PA-34 PA-39", ("pa", "Elmas —"): "PA-33 PA-34 PA-39",
    ("smc", "FVG ("): "SM-60", ("smc", "Order block ("): "SM-40 SM-41 SM-42", ("smc", "Breaker ("): "SM-50 SM-51",
    ("smc", "Range ve deviasyon —"): "SM-20 SM-22", ("smc", "SFP —"): "SM-30", ("smc", "Arz bölgesi"): "SM-10",
    ("smc", "Eşit tepe/dip"): "SM-70", ("smc", "Kilit seviyeler"): "SM-80 SM-83", ("smc", "Power of 3 —"): "SM-90 SM-91",
    ("pro", "Hacim profili"): "PR-01 PR-02", ("pro", "NPOC"): "PR-10", ("pro", "RSI"): "PR-20 PR-23", ("pro", "CVD"): "PR-40",
    ("pro", "Emilim"): "PR-42", ("pro", "FVG: %50"): "PR-30 PR-31", ("pro", "SFP 1d"): "PR-60 PR-60a", ("pro", "SFP 4h"): "PR-60",
    ("pro", "Son CME"): "PR-50", ("pro", "Open interest"): "PR-70 SM-95",
    ("mentor", "Pazartesi EXT"): "MB-20", ("mentor", "Hafta EXT"): "MB-20", ("mentor", "Kaos"): "MB-10",
    ("kitap", "Günlük VWAP"): "BK-01 BK-04 BK-10", ("kitap", "Hacimli kırılım"): "BK-25",
}


@dataclass
class Rule:
    id: str
    kind: str
    words: str
    extra: str
    group: str


@dataclass
class Picture:
    title: str
    body: str
    real: bool
    rules: list[str] = field(default_factory=list)


def cells(row: str) -> list[str]:
    return [c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row.strip().strip("|"))]


def read_rules(text: str) -> list[Rule]:
    """Rows of the tables whose first column is a rule number; the header names the columns, the last heading is the group."""
    out, group, head = [], "", []
    for line in text.split("\n"):
        if line.startswith("#"):
            group = line.lstrip("# ").strip()
        elif re.match(r"^\*\*[^*]+\*\*$", line.strip()):
            group = line.strip().strip("*")
        elif not line.startswith("|"):
            head = []                                  # a table ended; the next one is a rule list only if its first column is "No"
        elif re.match(r"^\|\s*No\s*\|", line):
            head = cells(line)
        elif not head:
            continue
        elif m := re.match(rf"^\|\s*({ID})\s*\|", line):
            row = dict(zip(head, cells(line)))
            words = next((row[k] for k in ("Kural", "Kılavuz", "Ders", "Bulgu → bizde") if row.get(k)), "") or cells(line)[-1]
            rest = {k: v for k, v in row.items() if k not in ("No", "Tür") and v and v != words}
            out.append(Rule(m[1], row.get("Tür", ""), words, " · ".join(f"{k}: {v}" for k, v in rest.items()), group))
    return out


def numbers_in(text: str) -> list[str]:
    """Rule numbers in a picture's text; "SM-01…04" means all four."""
    found = []
    for m in re.finditer(rf"({ID})(?:\s*[…–]\s*(\d+))?", text):
        found.append(m[1])
        if m[2]:
            prefix, first = m[1].split("-")
            found += [f"{prefix}-{n:02d}" for n in range(int(first) + 1, int(m[2]) + 1)]
    return found


def read_pictures(key: str, page: str) -> list[Picture]:
    out = []
    for part in re.split(r"(?=<h2>)", page):
        real = "gerçek grafikte" in part[:200]
        for body in re.findall(r"<figure.*?</figure>", part, re.S):
            title = html.unescape(re.sub("<.*?>", "", re.search(r"<h3>(.*?)</h3>", body, re.S)[1]))
            plain = re.sub(r"<svg.*?</svg>", "", body, flags=re.S)
            findings = re.findall(rf'<li class="(\w+)">({ID})', plain)
            broken = [i for c, i in findings if c == "violation"]
            checked = broken or [i for c, i in findings if c in ("ok", "guide")]
            linked = next((v.split() for (k, start), v in LINKS.items() if k == key and title.startswith(start)), [])
            written = numbers_in(re.sub("<.*?>", " ", re.sub(r"<ul>.*?</ul>", "", plain, flags=re.S)))
            out.append(Picture(title, body, real, list(dict.fromkeys(linked + written + ([] if linked else checked)))))
    return out


def rich(text: str) -> str:
    """The little Markdown the lists use: bold, code, links (shown as text)."""
    text = html.escape(text, quote=False)
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<i>\1</i>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)


KIND = {"K": "kesin", "R": "kılavuz", "T": "test edilir", "F": "filtre", "D": "davranış", "–": "not"}


def rule_html(r: Rule) -> str:
    kind = f'<span class="kind">{KIND.get(r.kind, r.kind)}</span>' if r.kind else ""
    extra = f'<div class="extra">{rich(r.extra)}</div>' if r.extra else ""
    return f'<li class="rule" data-id="{r.id}"><b class="no">{r.id}</b> {kind}<div>{rich(r.words)}</div>{extra}</li>'


def family_html(f: Family) -> tuple[str, int, int, int]:
    rules = read_rules((HERE / f.words).read_text(encoding="utf-8"))
    by_id = {r.id: r for r in rules}
    pictures = read_pictures(f.key, (HERE / f.pictures).read_text(encoding="utf-8")) if f.pictures else []
    blocks, shown = [], set()
    for p in pictures:
        own = [by_id[i] for i in p.rules if i in by_id]
        shown |= {r.id for r in own}
        items = "".join(rule_html(r) for r in own) or '<li class="rule">Bu görsel tek bir numaralı kurala bağlı değil.</li>'
        tag = '<span class="tag real">gerçek veri</span>' if p.real else '<span class="tag">çizim</span>'
        blocks.append(f'<div class="pair">{p.body}<div class="words">{tag}<ul>{items}</ul></div></div>')
    bare, group = [], None
    for r in rules:
        if r.id not in shown:
            if r.group != group:
                group = r.group
                bare.append(f'<li class="group">{rich(group)}</li>')
            bare.append(rule_html(r))
    rest = (f'<h3 class="sub">Görseli olmayan kurallar ({len(rules) - len(shown)})</h3><ul class="bare">{"".join(bare)}</ul>'
            if len(rules) > len(shown) else "")
    head = f'<h2 id="{f.key}">{f.name}: {len(rules)} kural, {len(shown)} görselli, {len(pictures)} görsel</h2>'
    return f'<section>{head}{"".join(blocks)}{rest}</section>', len(rules), len(shown), len(pictures)


EXTRA_CSS = """
.top{position:sticky;top:0;background:var(--bg);padding:10px 0;z-index:2;border-bottom:1px solid var(--grid)}
.top input{font:inherit;width:min(420px,100%);padding:8px 10px;border:1px solid var(--grid);border-radius:6px;background:var(--card);color:var(--ink)}
.top a{margin-right:12px;color:var(--motive);white-space:nowrap}
table.sum{border-collapse:collapse;margin:8px 0 14px;font-variant-numeric:tabular-nums}.sum td,.sum th{padding:4px 14px 4px 0;text-align:right;border-bottom:1px solid var(--grid)}
.sum td:first-child,.sum th:first-child{text-align:left}
.pair{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:16px;margin:0 0 16px;align-items:start}
.pair .wide+.words{grid-column:1/-1}.pair .words{padding-top:6px}.pair ul,.bare{list-style:none;padding:0;margin:6px 0 0;font-size:14.5px}
.rule{padding:7px 0;border-bottom:1px solid var(--grid)}.no{font:600 13px ui-monospace,Consolas,monospace;color:var(--motive)}
.kind,.tag{font-size:12px;color:var(--muted);border:1px solid var(--grid);border-radius:4px;padding:0 6px}.tag.real{color:var(--good);border-color:var(--good)}
.extra{font-size:13px;color:var(--muted)}.group{font-weight:600;padding:14px 0 2px}.sub{margin:26px 0 0;font-size:16px}h2{scroll-margin-top:70px}
code{font-size:.9em}@media (max-width:820px){.pair{grid-template-columns:1fr}}
"""
SCRIPT = """
const q=document.getElementById('q');q.addEventListener('input',()=>{const t=q.value.trim().toLocaleLowerCase('tr');
const hit=e=>!t||e.textContent.toLocaleLowerCase('tr').includes(t);
document.querySelectorAll('.pair').forEach(e=>e.style.display=hit(e)?'':'none');
document.querySelectorAll('.bare .rule').forEach(e=>e.style.display=hit(e)?'':'none');
document.querySelectorAll('.bare .group').forEach(e=>e.style.display=t?'none':'');});
"""


def build() -> tuple[str, list[tuple[str, int, int, int]]]:
    parts, rows = [], []
    for f in FAMILIES:
        body, n, shown, pictures = family_html(f)
        parts.append(body)
        rows.append((f.name, n, shown, pictures))
    total = ("Toplam", *[sum(r[i] for r in rows) for i in (1, 2, 3)])
    table = "".join(f"<tr><td>{a}</td><td>{b}</td><td>{c}</td><td>{b - c}</td><td>{d}</td></tr>" for a, b, c, d in [*rows, total])
    nav = "".join(f'<a href="#{f.key}">{f.name}</a>' for f in FAMILIES)
    page = (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>4.4 kural kataloğu</title><style>{CSS}{CHART_CSS}{EXTRA_CSS}</style></head><body><main><h1>4.4 kural kataloğu</h1>"
            '<p class="lead">Her görselin yanında anlattığı kurallar; sonra o ailenin görseli olmayan kuralları. Sözler kural listelerinden, '
            "görseller görsel sayfalarından gelir. Görsel bir kuralı gösterir, kazandırdığını kanıtlamaz.</p>"
            '<table class="sum"><tr><th>Aile</th><th>Kural</th><th>Görselli</th><th>Görselsiz</th><th>Görsel</th></tr>' + table + "</table>"
            f'<div class="top"><input id="q" type="search" placeholder="Ara: PR-60, SFP, stop…" aria-label="Kural ara"><div>{nav}</div></div>'
            + "".join(parts) + f"</main><script>{SCRIPT}</script></body></html>")
    return page, [*rows, total]


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    page, rows = build()
    path = HERE / "all-rules.html"
    path.write_text(page, encoding="utf-8")
    for name, n, shown, pictures in rows:
        print(f"{name:18} kural {n:4}  görselli {shown:4}  görsel {pictures:4}")
    print(path)


if __name__ == "__main__":
    main()
