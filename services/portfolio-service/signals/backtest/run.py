"""Run the 4.4 backtest on the local data and write the calibration report (RULES.md 9).

  .\\venv\\Scripts\\python.exe -m signals.backtest.run
writes data/reports/backtest-<date>.md (git-ignored, rebuilt from the same files = same result) and prints a summary.

Per asset and setup timeframe (1D and 4h): ZigZag (3 x ATR14) -> Elliott and harmonic setups -> each simulated with the
three entry variants; LTF confirmations from the 1h data. The calibration / test split is at 70% of each series' time
range: rules and settings may only be tuned on the first part, the second part is reported untouched.
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone

from signals.backtest.engine import CLOSE_LTF, VARIANTS, Params, simulate
from signals.backtest.ltf import LtfSignals
from signals.backtest.report import build_rows, markdown
from signals.backtest.setups import elliott_setups, harmonic_setups
from signals.data.candles import load_series
from signals.data.download import SERVICE_DIR
from signals.structure.zigzag import zigzag

ZIGZAG_MULTIPLE = 3.0
SPLIT_SHARE = 0.7
RUNS = [("BTCUSDT", "1d", timedelta(days=1)), ("BTCUSDT", "4h", timedelta(hours=4)),
        ("GC", "1d", timedelta(days=1)), ("GC", "4h", timedelta(hours=4)),
        ("ES", "1d", timedelta(days=1)), ("ES", "4h", timedelta(hours=4))]


def run(params: Params = Params()) -> tuple[str, list]:
    all_rows, notes = [], []
    ltf_cache: dict[str, LtfSignals] = {}
    for asset, timeframe, span in RUNS:
        candles = load_series(asset, timeframe).candles
        if len(candles) < 200:
            continue
        points = zigzag(candles, multiple=ZIGZAG_MULTIPLE)
        setups = elliott_setups(candles, points, asset, timeframe) + harmonic_setups(candles, points, asset, timeframe)
        if asset not in ltf_cache:
            ltf_cache[asset] = LtfSignals(load_series(asset, "1h").candles)
        ltf = ltf_cache[asset]

        def ltf_check(start, end, direction):
            return ltf.covers(start, end) and ltf(start, end, direction)

        trades = []
        for setup in setups:
            for variant in VARIANTS:
                trade = simulate(candles, setup, variant, params, ltf_check if variant == CLOSE_LTF else None, span)
                if trade is not None:
                    trades.append(trade)
        first, last = candles[0].time, candles[-1].time
        split = first + (last - first) * SPLIT_SHARE
        all_rows += build_rows(trades, candles, split, params)
        notes.append(f"- {asset} {timeframe}: {len(candles)} mum, {len(points)} ZigZag noktası, {len(setups)} kurulum, "
                     f"{len(trades)} işlem; ayrım {split:%Y-%m-%d}; 1h onay verisi {ltf.first:%Y-%m-%d}'den")

    today = datetime.now(timezone.utc)
    header = "\n".join([
        f"# 4.4 backtest — kalibrasyon raporu ({today:%Y-%m-%d})", "",
        "Veri: `data/raw/manifest.json` (Binance BTCUSDT, Yahoo GC=F / ES=F). Kurallar: `signals/RULES.md`.",
        f"Ayarlar: ZigZag {ZIGZAG_MULTIPLE} × ATR14; bölge bekleme {params.max_wait}, onay {params.confirm_bars}, "
        f"tutma {params.max_hold} mum; ücret taraf başına %{100 * params.fee:.1f}; aynı mumda hedef ve stop → stop.",
        "Başarı = hedef stoptan önce. Puan v0 = test örneğinin başarı oranının %95 alt sınırı × 100.", "",
        *notes])
    return markdown(all_rows, header), all_rows


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")        # the Windows console default (cp1254) cannot print the report
    report, rows = run()
    out_dir = SERVICE_DIR / "data" / "reports"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"backtest-{datetime.now(timezone.utc):%Y%m%d}.md"
    path.write_text(report, encoding="utf-8")
    print(report)
    print(f"\nreport: {path}")


if __name__ == "__main__":
    main()
