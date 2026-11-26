r"""One real chart where a rule worked and one where it did not, for every rule, timeframe and asset (confirm.py's candidates).

  .\venv\Scripts\python.exe -m signals.scoring.gallery          -> data/gallery/index.html (local, git-ignored)

Every chart draws what the code saw (wave labels, X-A-B-C-D, the divergence under the price, the level, the fib) and says in words why the
case counts as worked / not worked. The newest case is taken; the dates Aykut showed himself are left out.
"""

from __future__ import annotations

import html
import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from signals.data.candles import TIMEFRAMES
from signals.data.download import SERVICE_DIR
from signals.rules import pa_detect
from signals.scoring.confirm import ASSETS, BANDS, DEGREES, TAKE_AT, bars_of, stop_percent, Frame, elliott, five_waves, harmonics, shared_levels
from signals.scoring.confirm_report import NAME, ORDER, load, pct
from signals.scoring.run import OUT
from signals.scoring.turns import load_full
from signals.structure.pivots import HIGH
from signals.structure.zigzag import SwingPoint

FOLDER = SERVICE_DIR / "data" / "gallery"
SKIP = {"2026-09-21", "2026-10-02", "2026-10-15", "2026-10-16", "2026-10-21", "2026-11-04", "2026-04-27", "2026-03-04", "2026-03-05", "2026-07-01"}
W, H, PANEL = 560, 250, 70


class Evidence:
    def __init__(self):
        self.points: list[tuple[int, float, str]] = []
        self.lines: list[tuple[int, float, int, float, str]] = []
        self.levels: list[tuple[float, str, int]] = []        # price, name, first bar
        self.panel: tuple[str, np.ndarray, int, int] | None = None
        self.words = ""
        self.until: int | None = None                          # bar the picture must reach


WAVES = {"12345 sonu": ("0", "1", "2", "3", "4", "5"), "4. dalga sonu": ("0", "1", "2", "3", "4"), "ABC sonu": ("5", "A", "B", "C"), "B sonu": ("5", "A", "B"),
         "ABCDE üçgen sonu": ("5", "A", "B", "C", "D", "E"), ("X sonu", "tek bacak X"): ("5", "a", "b", "W", "X"), ("X sonu", "ABC X"): ("5", "a", "b", "W", "a", "b", "X"),
         ("WXY sonu", "tek bacak X"): ("5", "a", "b", "W", "X", "a", "b", "Y"), ("WXY sonu", "ABC X"): ("5", "a", "b", "W", "a", "b", "X", "a", "b", "Y"),
         ("WXYXZ sonu", "tek bacak X"): ("5", "a", "b", "W", "X", "a", "b", "Y", "X", "a", "b", "Z"),
         ("WXYXZ sonu", "ABC X"): ("5", "a", "b", "W", "a", "b", "X", "a", "b", "Y", "a", "b", "X", "a", "b", "Z")}


def fmt(p: float) -> str:
    return f"{p:,.0f}".replace(",", ".") if p >= 1000 else f"{p:.2f}"


def evidence(fr: Frame, tag: str, j: int, conf: int, price: float, side: int) -> Evidence:
    e, x, b = Evidence(), fr.x, fr.x.bars
    cat, rule, var = tag.split("|")
    kind, atr, hi = HIGH if side == -1 else "low", b.atr[j - 1], (b.high if side == -1 else -b.low)
    top = "tepe" if side == -1 else "dip"
    if cat in ("Elliott", "Harmonik"):
        for m in DEGREES:
            pts = fr.points(m, j, price, kind, conf)
            if len(pts) < 4:
                continue
            if cat == "Elliott":
                found = elliott(pts, fr.ended, conf)
                inner = var.startswith("iç yapı")
                if not (f"{rule}|{var}" in found or (inner and any(f.startswith(rule) for f in found))):
                    continue
                labels = WAVES.get(rule) or WAVES[(rule, var)]
                if inner and not fr.inner(pts[-len(labels):]):
                    continue
                run = pts[-len(labels):]
                if rule not in ("12345 sonu", "4. dalga sonu"):                                              # show the impulse it follows
                    before = fr.impulse.get(run[0].index)
                    i = len(pts) - len(labels)
                    if before is None and i >= 5 and five_waves(pts[i - 5:i + 1]):
                        before = pts[i - 5:i + 1]
                    e.points += [(p.index, p.price, n) for p, n in zip(before or [], ("0", "1", "2", "3", "4"))]
                e.points += [(p.index, p.price, n) for p, n in zip(run, labels)]
                e.words = f"{rule}: {var}. " + " → ".join(f"{n} {fmt(p.price)}" for p, n in zip(run, labels))
                break
            if rule in harmonics(pts):
                run = pts[-4:] if rule == "AB=CD" else pts[-5:]
                labels = "ABCD" if rule == "AB=CD" else "XABCD"
                e.points = [(p.index, p.price, n) for p, n in zip(run, labels)]
                q = [p.price for p in run]
                if rule == "AB=CD":
                    e.words = f"AB=CD: CD / AB = {abs(q[3] - q[2]) / abs(q[1] - q[0]):.2f}"
                else:
                    r = lambda a, c: abs(a) / abs(c)
                    xd = r(q[3] - q[4], q[3] - q[0]) if rule == "Cypher" else r(q[1] - q[4], q[1] - q[0])
                    e.words = f"{rule}: XB {r(q[1] - q[2], q[1] - q[0]):.3f}, AC {r(q[3] - q[2], q[1] - q[2]):.3f}, BD {r(q[4] - q[3], q[3] - q[2]):.3f}, XD {xd:.3f}"
                break
    elif cat == "Uyumsuzluk":
        series = fr.cvd if rule == "CVD" else b.volume if rule == "hacim" else fr.rsi
        name = {"CVD": "CVD", "hacim": "Hacim"}.get(rule, "RSI 14")
        a = max(0, j - 60)
        u = a + int(np.nanargmax(fr.rsi[a:j - 1] * (1 if side == -1 else -1))) if rule == "RSI" else a + int(hi[a:j - 2].argmax())
        if var == "gösterge etiketi":
            for d in (x.cvd_div if rule == "CVD" else x.divergences) if rule != "Trend Devam (gizli)" else x.divergences + x.cvd_div:
                if abs(d.pivot_index - j) <= 1:
                    u = d.previous_index
                    if d.oscillator == "CVD":
                        series, name = fr.cvd, "CVD"
        e.panel = (name, series, u, j)
        e.points = [(u, float(b.high[u] if side == -1 else b.low[u]), "1"), (j, price, "2")]
        e.words = f"Fiyat {fmt(e.points[0][1])} → {fmt(price)}, {name} {series[u]:,.1f} → {series[j]:,.1f}: " + ("fiyat geri kaldı, gösterge güçlü (trend devam)" if rule.startswith("Trend") else "fiyat yeni uç yaptı, gösterge yapmadı")
    elif cat == "SFP":
        for sweep, done, pivot, extreme in fr.sfp[side]:
            if j - 1 <= sweep <= j and done <= conf and abs(extreme - price) <= 0.05 * atr:
                level = float(b.high[pivot] if side == -1 else b.low[pivot])
                e.lines.append((pivot, level, sweep, level, "süpürülen seviye"))
                e.points = [(pivot, level, "eski"), (sweep, price, "SFP")]
                e.panel = ("RSI 14", fr.rsi, pivot, sweep)
                e.words = f"{fmt(level)} geçildi, {top} {fmt(price)}, kapanış geri döndü. RSI {fr.rsi[pivot]:.1f} → {fr.rsi[sweep]:.1f}" + (f", hacim {b.volume[pivot]:,.0f} → {b.volume[sweep]:,.0f}" if fr.volume else "")
    elif cat == "Fibonacci" and rule.startswith("reshort"):
        lo, high = BANDS[var]
        for m, r in fr.reshort(j, price, side).items():
            if lo <= r <= high:
                a = max(0, j - 600)
                over = np.nonzero(b.high[a:j] >= price)[0] if side == -1 else np.nonzero(b.low[a:j] <= price)[0]
                s = a + int(over[-1]) + 1 if len(over) else a
                k = s + int(b.low[s:j].argmin() if side == -1 else b.high[s:j].argmax())
                end = float(b.low[k] if side == -1 else b.high[k])
                begin = price + (end - price) / r * (r - 1) if r else price                           # 1 of the fib
                begin = end + (price - end) / r
                q = next(i for i in range(k, -1, -1) if (b.high[i] if side == -1 else b.low[i]) == begin or abs((b.high[i] if side == -1 else b.low[i]) - begin) < 1e-6 * begin)
                e.points = [(q, begin, "1"), (k, end, "0"), (j, price, f"{r:.3f}")]
                e.levels = [(end + v * (begin - end), f"{v:g}", k) for v in (0.382, 0.5, 0.618, 0.66, 0.786, 0.886)]
                e.words = f"{'Reshort' if side == -1 else 'Relong'}: {fmt(begin)} → {fmt(end)} bacağının {r:.3f}'ine dönüş (bölge {var})"
                break
    elif cat == "Fibonacci":
        want = float(var.replace(",", "."))
        for m in DEGREES:
            pts = fr.points(m, j, price, kind, conf)
            if len(pts) >= 4:
                p0, p1, p2 = pts[-4], pts[-3], pts[-2]
                s = -side
                if s * p2.price > s * p0.price and s * (p1.price - p0.price) > 0 and abs((price - p2.price) / (p1.price - p0.price) - want) <= 0.03:
                    e.points = [(p0.index, p0.price, "0"), (p1.index, p1.price, "1"), (p2.index, p2.price, "2"), (j, price, var)]
                    e.levels = [(p2.price + v * (p1.price - p0.price), f"{v:g}", p2.index) for v in sorted({1.0, 1.272, 1.618, want})]
                    e.words = f"Trend fib 0-1-2: {fmt(p0.price)}, {fmt(p1.price)}, {fmt(p2.price)}; fiyat {var} hedefine ({fmt(price)}) geldi"
                    break
    elif cat == "Price action" and rule in (pa_detect.RISING_WEDGE, pa_detect.FALLING_WEDGE, pa_detect.SYMMETRIC):
        for m in DEGREES:
            pts = fr.points(m, j, price, kind, conf)
            if len(pts) < 5:
                continue
            shift = max(0, pts[-5].index - 1)
            for pat in pa_detect.converging_patterns(x.candles[shift:j + 1], [SwingPoint(p.kind, p.index - shift, p.price, j - shift) for p in pts[-5:]]):
                if pat.kind == rule:
                    a, z = pts[-5].index, min(j + 12, len(x.candles) - 1)
                    e.points = [(p.index, p.price, str(i + 1)) for i, p in enumerate(pts[-5:])]
                    e.lines = [(a, pat.line(n, a - shift), z, pat.line(n, z - shift), "") for n in ("upper", "lower")]
                    e.words = f"{rule}: 5 temas, {top} çizgide"
                    return e
    elif cat == "Price action" and rule == "trend çizgisi":
        for line, k, end, d in fr.lines:
            if d == side and k < j <= end and j - line.touches[-1].index < 300 and abs(line.at(j) - price) <= 0.3 * atr:
                e.points = [(p.index, p.price, str(i + 1)) for i, p in enumerate(line.touches)] + [(j, price, "4")]
                e.lines = [(line.touches[0].index, line.at(line.touches[0].index), j + 5, line.at(j + 5), "")]
                e.words = "Üç temaslı trend çizgisine yeni temas"
    elif cat == "Price action" and rule == "mum":
        e.points, e.words = [(j, price, var)], f"{var} mumu {top}te"
    elif cat == "Funding":
        e.words = f"Funding {'≥ +%0,05 (aşırı long)' if side == -1 else '≤ −%0,05 (aşırı short)'}"
    if not e.words:
        lv = fr.levels.get(tag)
        if lv is not None:
            when = fr.t[j] + fr.span
            ok = np.nonzero((lv.side == side) & (lv.known < when) & (lv.until >= when) & (np.abs(lv.price - price) <= 0.3 * atr))[0]
            if len(ok):
                i = ok[np.abs(lv.price[ok] - price).argmin()]
                first = max(0, int(np.searchsorted(fr.t, lv.known[i])) - 1)
                e.levels = [(float(lv.price[i]), f"{rule} {var}".strip(), first)]
                e.words = f"{rule} {var}: {fmt(float(lv.price[i]))}; {top} {fmt(price)}"
    if not any(i == j for i, _, _ in e.points):
        e.points.append((j, price, top))
    return e


def draw(fr: Frame, e: Evidence, j: int, price: float, side: int, thr: float, worked: bool, hit: int | None) -> str:
    b, n = fr.x.bars, len(fr.x.candles)
    marks = [i for i, _, _ in e.points] + [i for a in e.lines for i in (a[0],)] + [max(f, j - 60) for _, _, f in e.levels]
    a, z = max(0, min(marks + [j]) - 8, j - 420), min(n - 1, max(j + bars_of(fr.f), min(e.until or 0, j + 300)) + 4)
    m = z - a + 1
    lo, hi = float(b.low[a:z + 1].min()), float(b.high[a:z + 1].max())
    target = price + side * thr
    lo, hi = min(lo, target), max(hi, target)
    X = lambda i: round(6 + (i - a) / max(1, m - 1) * (W - 60), 1)
    Y = lambda p: round(12 + (hi - p) / ((hi - lo) or 1) * (H - 24), 1)
    w = max(0.7, min(5.0, (W - 60) / m * 0.6))
    paths = {"u": [], "d": [], "k": []}
    for i in range(a, z + 1):
        paths["k"].append(f"M{X(i)} {Y(b.high[i])}V{Y(b.low[i])}")
        up = b.close[i] >= b.open[i]
        t, s = Y(max(b.open[i], b.close[i])), Y(min(b.open[i], b.close[i]))
        paths["u" if up else "d"].append(f"M{X(i)} {t}V{max(s, t + 0.6)}")
    total = H + (PANEL if e.panel else 0)
    out = [f'<svg viewBox="0 0 {W} {total}"><path class="k" d="{"".join(paths["k"])}"/><path class="u" style="stroke-width:{w:.1f}" d="{"".join(paths["u"])}"/><path class="dn" style="stroke-width:{w:.1f}" d="{"".join(paths["d"])}"/>']
    out.append(f'<line class="stop" x1="{X(j)}" x2="{X(z)}" y1="{Y(price)}" y2="{Y(price)}"/><line class="tgt" x1="{X(j)}" x2="{X(z)}" y1="{Y(target)}" y2="{Y(target)}"/>'
               f'<text class="r" x="{W - 50}" y="{Y(target) + 4}">hedef</text>')
    for p, name, first in e.levels:
        if lo <= p <= hi:
            out.append(f'<line class="lv" x1="{X(max(a, first))}" x2="{X(z)}" y1="{Y(p)}" y2="{Y(p)}"/><text class="lt" x="{W - 50}" y="{Y(p) - 2}">{html.escape(name[:22])}</text>')
    for i, p, k, q, _ in e.lines:
        out.append(f'<line class="ln" x1="{X(max(a, i))}" y1="{Y(p)}" x2="{X(min(z, k))}" y2="{Y(q)}"/>')
    pts = [p for p in e.points if a <= p[0] <= z]
    if len(pts) >= 3:
        out.append(f'<polyline class="ln" points="{" ".join(f"{X(i)},{Y(p)}" for i, p, _ in pts)}"/>')
    for i, p, name in pts:
        above = p >= (b.high[i] + b.low[i]) / 2
        out.append(f'<circle class="pt" cx="{X(i)}" cy="{Y(p)}" r="2.4"/><text class="nm" x="{X(i)}" y="{Y(p) + (-5 if above else 12)}">{html.escape(name)}</text>')
    if hit is not None and a <= hit <= z:
        out.append(f'<circle class="{"ok" if worked else "no"}" cx="{X(hit)}" cy="{Y(target if worked else price)}" r="4"/>')
    if e.panel:
        name, v, u, k = e.panel
        seg = np.array(v[a:z + 1], dtype=float)
        mn, mx = float(np.nanmin(seg)), float(np.nanmax(seg))
        PY = lambda q: round(H + PANEL - 6 - (q - mn) / ((mx - mn) or 1) * (PANEL - 14), 1)
        out.append(f'<text class="lt" x="6" y="{H + 8}">{name}</text><polyline class="os" points="{" ".join(f"{X(a + i)},{PY(q)}" for i, q in enumerate(seg) if not np.isnan(q))}"/>')
        if u >= a and not np.isnan(v[u]) and not np.isnan(v[k]):
            out.append(f'<line class="dv" x1="{X(u)}" y1="{PY(v[u])}" x2="{X(k)}" y2="{PY(v[k])}"/>')
    return "".join(out) + "</svg>"


def chart(fr: Frame, tag: str, row: list, j: int, conf: int) -> str:
    t, side, move, worked, after, _, _, _ = row
    b = fr.x.bars
    price, entry = float(b.high[j] if side == -1 else b.low[j]), float(b.close[j])
    d = stop_percent(fr.asset, entry, price)          # Aykut's trade: the stop above the top with room for a sweep
    thr_pct, stop = TAKE_AT * d, entry * (1 - side * d / 100)
    thr = thr_pct / 100 * entry
    e = evidence(fr, tag, j, conf, price, side)
    end = min(len(b.close) - 1, j + bars_of(fr.f))
    over = np.nonzero(b.high[j + 1:end + 1] >= stop)[0] if side == -1 else np.nonzero(b.low[j + 1:end + 1] <= stop)[0]
    reach = np.nonzero(b.low[j + 1:end + 1] <= entry - thr)[0] if side == -1 else np.nonzero(b.high[j + 1:end + 1] >= entry + thr)[0]
    hit = j + 1 + int((reach if worked else over)[0]) if len(reach if worked else over) else None
    e.until = hit
    top, moved = ("tepe", "düştü") if side == -1 else ("dip", "yükseldi")
    if worked:
        why = f"Başarılı: stop (%{d:.1f}) görülmeden girişten %{move:.1f} {moved} (yarı kâr için gereken %{thr_pct:.1f})" + (f", {hit - j} mumda hedef" if hit else "")
    elif len(over):
        why = f"Başarısız: en çok %{move:.1f} {moved} (gereken %{thr_pct:.1f}), {over[0] + 1} mum sonra stop (%{d:.1f}) geldi"
    else:
        why = f"Başarısız: stop gelmedi ama hareket yetmedi: %{move:.1f} (gereken %{thr_pct:.1f})"
    return (f'<figure class="{"win" if worked else "loss"}">{draw(fr, e, j, entry, side, thr, worked, hit)}<figcaption><b>{fr.x.times[j]:%d.%m.%Y %H:%M}</b> UTC · {top} {fmt(price)}<br>{html.escape(e.words)}'
            f'<br><span class="{"ok" if worked else "no"}">{html.escape(why)}</span></figcaption></figure>')


def job(asset: str, f: str) -> dict:
    """tag -> (worked chart, failed chart) on one timeframe."""
    rows = load(asset, 0).get(f, [])
    if not rows:
        return {}
    cache = load_full(asset)
    fr = Frame(asset, f, cache, shared_levels(asset, cache))
    at = {float(t): i for i, t in enumerate(fr.t)}
    picked: dict[str, dict[bool, list]] = {}
    for r in reversed(rows):
        if fr.x.times[at[r[0]]].strftime("%Y-%m-%d") in SKIP:
            continue
        for tag in r[6]:
            picked.setdefault(tag, {}).setdefault(bool(r[3]), r)
    out = {}
    for tag, by in picked.items():
        out[tag] = {}
        for worked, r in by.items():
            j = at[r[0]]
            try:
                out[tag]["1" if worked else "0"] = chart(fr, tag, r, j, j)
            except Exception as error:
                out[tag]["1" if worked else "0"] = f'<p class="no">Çizilemedi: {type(error).__name__} {html.escape(str(error))}</p>'
    return out


CSS = """
:root{color-scheme:light dark;--bg:#fff;--ink:#1b1c1f;--muted:#6b6f76;--grid:#ddd;--up:#1f9d6b;--dn:#d04a4a;--acc:#2f6fde;--warn:#c98a12}
@media (prefers-color-scheme:dark){:root{--bg:#121316;--ink:#e8e9ec;--muted:#9a9fa8;--grid:#2b2e34;--up:#37b98a;--dn:#e06464;--acc:#6ea0ff;--warn:#e0a83a}}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 system-ui,Segoe UI,sans-serif}main{max-width:1240px;margin:0 auto;padding:20px 16px}
h2{margin:34px 0 6px;font-size:20px}h3{margin:18px 0 4px;font-size:15px}.row{display:grid;grid-template-columns:1fr 1fr;gap:14px;content-visibility:auto;contain-intrinsic-size:0 360px}
figure{margin:0;border:1px solid var(--grid);border-radius:8px;padding:8px}figure.win{border-top:3px solid var(--up)}figure.loss{border-top:3px solid var(--dn)}figcaption{font-size:13px;color:var(--muted)}figcaption b{color:var(--ink)}
svg{width:100%;height:auto;display:block}.k{stroke:var(--muted);stroke-width:.6;fill:none}.u{stroke:var(--up);fill:none}.dn{stroke:var(--dn);fill:none}.stop{stroke:var(--dn);stroke-dasharray:4 3;stroke-width:1}
.tgt{stroke:var(--up);stroke-dasharray:4 3;stroke-width:1}.lv{stroke:var(--warn);stroke-width:1}.ln{stroke:var(--acc);stroke-width:1.5;fill:none}.pt{fill:var(--acc)}.nm{font-size:11px;font-weight:700;text-anchor:middle;fill:var(--ink)}
.lt,.r{font-size:9.5px;fill:var(--muted)}.os{stroke:var(--warn);fill:none;stroke-width:1}.dv{stroke:var(--acc);stroke-width:2}.ok{color:var(--up);fill:var(--up)}.no{color:var(--dn);fill:var(--dn)}a{color:var(--acc)}.none{color:var(--muted);font-size:13px}
.nav{position:sticky;top:0;background:var(--bg);padding:8px 0;border-bottom:1px solid var(--grid);z-index:2;font-size:14px}.nav a{margin-right:10px}@media (max-width:760px){.row{grid-template-columns:1fr}}
"""


def page(title: str, body: str, nav: str = "") -> str:
    return (f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head>'
            f'<body><main><h1>{title}</h1>{nav}{body}</main></body></html>')


def slug(s: str) -> str:
    return "".join(c if c.isascii() and c.isalnum() else "-" for c in s.lower().translate(str.maketrans("ıİşŞğĞçÇöÖüÜâ", "iIsSgGcCoOuUa")))


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    FOLDER.mkdir(parents=True, exist_ok=True)
    fit = json.loads((OUT / "confirm_points.json").read_text(encoding="utf-8"))["fit"]
    jobs = [(a, f) for a in ASSETS for f in TIMEFRAMES]
    with ProcessPoolExecutor(max_workers=4) as pool:
        got = dict(zip(jobs, pool.map(job, *zip(*jobs))))
    index, total = "", {"başarılı": 0, "başarısız": 0, "hata": 0}
    for a in ASSETS:
        tags = sorted({t for f in TIMEFRAMES for t in got[(a, f)]}, key=lambda t: (ORDER.index(t.split("|")[0]) if t.split("|")[0] in ORDER else 99, t))
        links = ""
        for cat in dict.fromkeys(t.split("|")[0] for t in tags):
            mine, body, nav = [t for t in tags if t.split("|")[0] == cat], "", ""
            for n, tag in enumerate(mine):
                _, rule, var = tag.split("|")
                title = f"{rule}{': ' + var if var else ''}"
                nav += f'<a href="#r{n}">{html.escape(title)}</a>'
                body += f'<h2 id="r{n}">{html.escape(title)}</h2>'
                for f in TIMEFRAMES:
                    ex = got[(a, f)].get(tag, {})
                    s = fit.get(f"{a} {f}", {}).get(tag if var else f"{cat}|{rule}", {})
                    rate = f'{pct(s["rate"])} çalıştı, bu onay yokken {pct(s["rest"])} ({s["n"]} kez)' if "rate" in s else f'{s.get("n", 0)} kez oluştu (oran için az)'
                    body += f'<h3>{f} <span class="none">{rate}</span></h3>'
                    if ex:
                        body += f'<div class="row">{ex.get("1", "<p class=none>Bu dilimde başarılı örnek yok.</p>")}{ex.get("0", "<p class=none>Bu dilimde başarısız örnek yok.</p>")}</div>'
                        total["başarılı"] += "1" in ex
                        total["başarısız"] += "0" in ex
                        total["hata"] += sum("Çizilemedi" in v for v in ex.values())
                    else:
                        body += '<p class="none">Bu dilimde hiç oluşmadı.</p>'
            name = f"{slug(NAME[a])}-{slug(cat)}.html"
            (FOLDER / name).write_text(page(f"{NAME[a]}: {cat}", body, f'<div class="nav"><a href="index.html">← hepsi</a>{nav}</div>'), encoding="utf-8")
            links += f'<li><a href="{name}">{cat}</a> ({len(mine)} kural)</li>'
        index += f"<h2>{NAME[a]}</h2><ul>{links}</ul>"
    lead = ('<p>Her kuralın her zaman diliminde biri <b>başarılı</b> (yeşil), biri <b>başarısız</b> (kırmızı) gerçek örneği: en yeni olanlar, senin gösterdiğin tarihler hariç. Kırmızı kesik çizgi: tepe/dip (geçilirse başarısız). '
            f'Yeşil kesik çizgi: gereken %2 hareket. Toplam {total["başarılı"]} başarılı, {total["başarısız"]} başarısız grafik.</p>')
    (FOLDER / "index.html").write_text(page("Kural galerisi", lead + index), encoding="utf-8")
    print(total)


if __name__ == "__main__":
    main()
