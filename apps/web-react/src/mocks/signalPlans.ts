import type { SignalPlan } from "../types/signals";

// SAMPLE DATA for the 4.4 screens (types/signals.ts is a draft, not a contract). Prices, levels and scores are
// illustrative, not the output of the 4.4 module; the backtest figures follow the shape of the v0 report
// (signals/reports/2026-11-23-v0.md: distinct setups, Wilson 95 % interval). Two assets clear the threshold and get a
// conditional plan, one does not, so both screen states can be built. F2 may extend this file.

const DISCLAIMER = "Bu bir işlem emri değil, koşullu bir plandır. Yatırım tavsiyesi değildir (YTD).";

export const SAMPLE_SIGNAL_PLANS: SignalPlan[] = [
  {
    asset: "GOLD",
    assetName: "Altın (COMEX vadeli, GC=F)",
    quoteCurrency: "USD",
    generatedAt: "2026-11-24T09:00:00Z",
    lastPrice: 4152,
    view: {
      bias: "BEARISH",
      timeframes: ["1W", "1D"],
      summary: "Günlükte yükseliş dalgası yorgun; fiyat 4.300 civarındaki direnç bölgesine yaklaşırsa düzeltme beklenir.",
    },
    plan: {
      direction: "SHORT",
      entryZone: { low: 4280, high: 4320 },
      ltfConfirmation: {
        timeframes: ["4h", "1h"],
        signals: ["SFP", "RSI_DIVERGENCE"],
        description: "Bölgede 1 saatlikte SFP ve RSI negatif uyumsuzluğu (N.U) aranır; onay yoksa plan beklemede kalır.",
      },
      targets: [4180, 4060],
      stop: 4365,
      description: "Altın 4.300 bölgesine gelirse alt zaman diliminde onay aranır; onay gelirse kısa (short) yönlü plan.",
    },
    levels: { invalidation: 4400, microInvalidation: 4365, keyLevel: 4300 },
    mainModel: {
      kind: "ELLIOTT_IMPULSE",
      name: "5 dalgalı itki, 5. dalga sonu",
      description: "5. dalga hedef bölgesi 4.280–4.320 ile Fibonacci 1,618 uzantısı çakışıyor.",
      fit: 74,
    },
    alternativeModel: {
      kind: "ELLIOTT_CORRECTION",
      name: "ABC düzeltmesi (flat)",
      description: "C dalgası 4.400'ün üstüne taşarsa yükseliş sürüyor demektir; ana model geçersiz olur.",
      fit: 48,
    },
    confirmation: {
      total: 76,
      threshold: 70,
      components: [
        { code: "HTF_TREND", label: "Üst zaman dilimi yönü", points: 18, max: 25 },
        { code: "FIB_ZONE", label: "Fibonacci bölgesi (0,618 / 0,786)", points: 20, max: 20 },
        { code: "RSI_DIVERGENCE", label: "RSI uyumsuzluğu", points: 14, max: 20 },
        { code: "SFP", label: "Likidite avı (SFP)", points: 14, max: 20 },
        { code: "REGIME_VETO", label: "Piyasa rejimi (veto yok)", points: 10, max: 15 },
      ],
    },
    backtest: {
      text: "Geçmiş testte benzer 41 kurulumun %44'ü hedefe ulaştı (%95 aralık: %30–%59). Örnek az; sonuç kesin değil.",
      sampleSize: 41,
      hitRate: 0.44,
      interval95: [0.3, 0.59],
      period: "2012–2026",
    },
    disclaimer: DISCLAIMER,
    isSample: true,
  },
  {
    asset: "BTC",
    assetName: "Bitcoin (BTCUSDT)",
    quoteCurrency: "USD",
    generatedAt: "2026-11-24T09:00:00Z",
    lastPrice: 91850,
    view: {
      bias: "BULLISH",
      timeframes: ["1W", "1D"],
      summary: "Haftalık yapı yukarı; günlükte düzeltme 0,618 geri çekilme bölgesine kadar sürebilir.",
    },
    plan: {
      direction: "LONG",
      entryZone: { low: 86500, high: 88000 },
      ltfConfirmation: {
        timeframes: ["4h", "1h"],
        signals: ["SFP", "CVD_DIVERGENCE", "CLOSE_CONFIRMATION"],
        description: "Bölgede 1 saatlikte SFP, CVD pozitif uyumsuzluğu ve 4 saatlik kapanış onayı aranır.",
      },
      targets: [95000, 99500],
      stop: 84900,
      description: "Bitcoin 86.500–88.000 bölgesine gerilerse alt zaman diliminde onay aranır; onay gelirse uzun (long) yönlü plan.",
    },
    levels: { invalidation: 83200, microInvalidation: 84900, keyLevel: 88000 },
    mainModel: {
      kind: "FIBONACCI",
      name: "Trend içi 0,618 geri çekilme",
      description: "Son yükseliş ayağının 0,618 seviyesi ile önceki haftalık zirve aynı bölgede.",
      fit: 71,
    },
    alternativeModel: {
      kind: "ELLIOTT_CORRECTION",
      name: "Derin ABC düzeltmesi",
      description: "83.200 altında günlük kapanış, düzeltmenin 0,786'ya uzadığını gösterir.",
      fit: 39,
    },
    confirmation: {
      total: 72,
      threshold: 70,
      components: [
        { code: "HTF_TREND", label: "Üst zaman dilimi yönü", points: 22, max: 25 },
        { code: "FIB_ZONE", label: "Fibonacci bölgesi (0,618 / 0,786)", points: 16, max: 20 },
        { code: "CVD_DIVERGENCE", label: "CVD uyumsuzluğu", points: 10, max: 20 },
        { code: "SFP", label: "Likidite avı (SFP)", points: 12, max: 20 },
        { code: "REGIME_VETO", label: "Piyasa rejimi (veto yok)", points: 12, max: 15 },
      ],
    },
    backtest: {
      text: "Geçmiş testte benzer 172 kurulumun %37'si hedefe ulaştı (%95 aralık: %30–%44). Bu oran rastgele girişten anlamlı biçimde iyi değil.",
      sampleSize: 172,
      hitRate: 0.37,
      interval95: [0.3, 0.44],
      period: "2017–2026",
    },
    disclaimer: DISCLAIMER,
    isSample: true,
  },
  {
    asset: "SPX",
    assetName: "S&P 500 (E-mini vadeli, ES=F)",
    quoteCurrency: "USD",
    generatedAt: "2026-11-24T09:00:00Z",
    lastPrice: 6712,
    view: {
      bias: "NEUTRAL",
      timeframes: ["1W", "1D"],
      summary: "Fiyat haftalık aralığın ortasında; yön için aralığın kırılması beklenmeli.",
    },
    plan: null,
    levels: { invalidation: 6480, microInvalidation: 6590, keyLevel: 6850 },
    mainModel: {
      kind: "RANGE",
      name: "Haftalık aralık",
      description: "6.590–6.850 aralığı korunuyor; kırılma 4 saatlik kapanışla teyit edilmeli.",
      fit: 62,
    },
    alternativeModel: null,
    confirmation: {
      total: 55,
      threshold: 70,
      components: [
        { code: "HTF_TREND", label: "Üst zaman dilimi yönü", points: 10, max: 25 },
        { code: "FIB_ZONE", label: "Fibonacci bölgesi (0,618 / 0,786)", points: 12, max: 20 },
        { code: "RSI_DIVERGENCE", label: "RSI uyumsuzluğu", points: 8, max: 20 },
        { code: "SFP", label: "Likidite avı (SFP)", points: 10, max: 20 },
        { code: "REGIME_VETO", label: "Piyasa rejimi (veto yok)", points: 15, max: 15 },
      ],
    },
    backtest: {
      text: "Onay puanı eşiğin altında olduğu için plan yok. Geçmiş testte benzer 58 kurulumun %34'ü hedefe ulaştı (%95 aralık: %23–%47).",
      sampleSize: 58,
      hitRate: 0.34,
      interval95: [0.23, 0.47],
      period: "2012–2026",
    },
    disclaimer: DISCLAIMER,
    isSample: true,
  },
];
