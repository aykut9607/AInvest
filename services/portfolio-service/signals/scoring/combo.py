r"""Rules together: does a lower-frame trigger work better when a higher-frame rule points the same way? (Aykut's system: HTF zone + LTF
confirmation)

  .\venv\Scripts\python.exe -m signals.scoring.combo           -> data/reports/combo.json

trigger   a signal on 15m / 30m / 1h / 2h (entry at its close, respect = 1 / 2 / 3 ATR of that frame)
context   a rule's event on 4h / 12h / 1d in the same direction that became known at most WINDOW bars of its frame ago; contexts of one
          family (fib, divergence, ...) are never counted twice
A pair counts only if it beats (a) the same pair on shuffled prices and (b) the same trigger without the context, on real prices.
Second part: the number of different families that agree, 0, 1, 2, ... and the respect rate at each count.
"""

from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor

import numpy as np

from signals.scoring.null import NO_VOLUME, null_cache
from signals.scoring.reaction import DOWN, KS, UP, find_touch, play
from signals.scoring.rule_events import SPAN, TESTS, Context, load_all
from signals.scoring.run import OUT, VOLUME

ASSETS = ("BTCUSDT", "XAU", "SPX")
LOW, HIGH_FRAMES, WINDOW = ("15m", "30m", "1h", "2h"), ("4h", "12h", "1d"), 6
SEEDS, CHECK = 4, 5
TRIGGERS = {"RSI uyumsuzluğu": ("rsi_pu", "rsi_nu"), "CVD uyumsuzluğu": ("cvd_pu", "cvd_nu"), "Trend Devam (gizli)": ("rsi_tdb", "rsi_tda"), "SFP": ("sfp",),
            "SFP + RSI": ("sfp_rsi",), "CHoCH": ("choch",), "MSB": ("msb",), "BOS": ("bos",), "Engulfing": ("engulf",), "Pin bar": ("pin",),
            "Trend çizgisi kırılımı": ("trendline_break",), "Kama / üçgen kırılımı": ("wedge_rising", "wedge_falling", "triangle_sym"), "Deviasyon": ("deviation",)}
# family -> name -> tests
CONTEXTS = {
    "yapı": {"MSB": ("msb",), "BOS": ("bos",), "CHoCH": ("choch",), "trend çizgisi kırılımı": ("trendline_break",)},
    "sfp": {"SFP": ("sfp",), "SFP + RSI": ("sfp_rsi",), "deviasyon": ("deviation",)},
    "uyumsuzluk": {"RSI P.U/N.U": ("rsi_pu", "rsi_nu"), "Trend Devam": ("rsi_tdb", "rsi_tda"), "CVD P.U/N.U": ("cvd_pu", "cvd_nu"), "hacim uyumsuzluğu": ("vol_pu", "vol_nu")},
    "fib": {"0,34–0,382": ("fr_0.34", "fr_0.382"), "0,5": ("fr_0.5",), "0,618–0,66": ("fr_0.618", "fr_0.66"), "0,709–0,786": ("fr_0.709", "fr_0.786"), "0,886": ("fr_0.886",)},
    "uzatma": {"trend fib hedefi 1,272–2,618 (tepki)": ("ft_1.272", "ft_1.414", "ft_1.618", "ft_2.0", "ft_2.618"), "1,272 ötesi kapanış (devam)": ("ft_trigger",)},
    "bölge": {"order block": ("ob",), "FVG": ("fvg",), "arz/talep": ("sd",), "breaker": ("breaker",), "gövde seviyesi": ("body_1d_2", "body_1w_1", "body_1w_2", "body_1M_1")},
    "elliott": {"5. dalga bölgesi": ("e_w5", "e_w5d"), "C bölgesi": ("e_zig", "e_flat"), "5 dalga bitti": ("e_done", "e_diag"), "4. dalga": ("e_w4",)},
    "harmonik": {"PRZ": ("h_all",)},
    "formasyon": {"kama/üçgen/elmas kırılımı": ("wedge_rising", "wedge_falling", "triangle_sym", "diamond")},
    "seviye": {"Pazartesi/hafta/ay bandı süpürme": ("ext_Pazartesi_sweep", "ext_Hafta_sweep", "ext_Ay_sweep"),
               "bant ötesi kapanış": ("ext_Pazartesi_break", "ext_Hafta_break", "ext_Ay_break"),
               "WO / MO yönü": ("bias_w", "bias_m"), "nPOC": ("npoc_d", "npoc_w"), "önceki gün/hafta VAH-POC-VAL": ("prev_d_VAH", "prev_d_POC", "prev_d_VAL", "prev_w_VAH", "prev_w_POC", "prev_w_VAL")},
}
BY_KEY = {t.key: t for t in TESTS}


def stream(x: Context, keys) -> list[tuple]:
    """(moment known, direction, entry bar, event) of these tests on one frame; a level event counts from the close of its touch bar."""
    out = []
    for key in keys:
        t = BY_KEY[key]
        if x.frame not in t.frames or (x.asset in NO_VOLUME and key.startswith(VOLUME)):
            continue
        events = t.run(x)
        for e in events[0] if isinstance(events, tuple) else events:
            i = e.index if e.price is None else find_touch(x.bars, e)
            if i is not None and i < len(x.candles):
                out.append((x.known(i), e.direction, i, e))
    return sorted(out, key=lambda r: r[0])


def contexts(x: Context) -> dict:
    """(frame, family, name) -> {direction: sorted known times}"""
    out = {}
    for f in HIGH_FRAMES:
        h = x.other(f)
        if h is None:
            continue
        for family, names in CONTEXTS.items():
            for name, keys in names.items():
                rows = stream(h, keys)
                out[(f, family, name)] = {d: np.array([r[0].timestamp() for r in rows if r[1] == d]) for d in (UP, DOWN)}
    return out


def active(times: np.ndarray, now: np.ndarray, window: float) -> np.ndarray:
    k = np.searchsorted(times, now, side="right") - 1
    return (k >= 0) & (now - times[np.maximum(k, 0)] <= window) if len(times) else np.zeros(len(now), dtype=bool)


def triggers(x: Context, keys, start: int = 0) -> list[tuple]:
    """Judged, non-overlapping cases of one trigger: (known time, direction, respected per k, bar)"""
    out, busy = [], {UP: -1, DOWN: -1}
    for known, d, i, e in stream(x, keys):
        if i <= busy[d] or i < start:
            continue
        r = play(x.bars, e)
        if r:
            busy[d] = r[1][0][1]
            out.append((known.timestamp(), d, [bool(w) for w, _ in r[1]], i))
    return out


def job(asset: str, seed: int) -> dict:
    cache = load_all(asset) if seed == 0 else null_cache(asset, seed)
    pairs, counts = {}, {}
    ctx = None
    for low in LOW:
        x = Context(asset, low, cache)
        if ctx is None:
            ctx = contexts(x)
        for name, keys in TRIGGERS.items():
            cases = triggers(x, keys)
            if len(cases) < 30:
                continue
            now, d = np.array([c[0] for c in cases]), np.array([c[1] for c in cases])
            won = np.array([c[2] for c in cases])
            pairs[f"{low}|{name}|-"] = [len(cases), won.sum(0).tolist()]
            families = {f: np.zeros(len(cases), dtype=bool) for f in CONTEXTS}
            against = {f: np.zeros(len(cases), dtype=bool) for f in CONTEXTS}
            for (hf, family, cname), by in ctx.items():
                w = WINDOW * SPAN[hf].total_seconds()
                on = np.where(d == UP, active(by[UP], now, w), active(by[DOWN], now, w))
                off = np.where(d == UP, active(by[DOWN], now, w), active(by[UP], now, w))
                families[family] |= on
                against[family] |= off
                if on.sum() >= 5:
                    pairs[f"{low}|{name}|{hf} {cname}"] = [int(on.sum()), won[on].sum(0).tolist()]
            score = sum((families[f] & ~against[f]).astype(int) - (against[f] & ~families[f]).astype(int) for f in CONTEXTS)
            for s in range(-6, 7):
                m = score == s
                if m.any():
                    n, w = counts.setdefault(f"{low}|{s}", [0, [0] * len(KS)])
                    counts[f"{low}|{s}"] = [n + int(m.sum()), [a + int(b) for a, b in zip(w, won[m].sum(0))]]
    return {"pairs": pairs, "counts": counts}


def main() -> None:
    jobs = [(a, s) for a in ASSETS for s in range(CHECK + 1)]
    with ProcessPoolExecutor(max_workers=4) as pool:
        got = dict(zip(jobs, pool.map(job, *zip(*jobs))))
    out = {a: {"real": got[(a, 0)], "check": got[(a, CHECK)], "null": [got[(a, s)] for s in range(1, SEEDS + 1)]} for a in ASSETS}
    (OUT / "combo.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    print("combo", {a: len(out[a]["real"]["pairs"]) for a in ASSETS})


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
