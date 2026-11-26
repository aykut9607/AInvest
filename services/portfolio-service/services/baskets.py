"""The numbers behind 4.1-4.3 and where each comes from (docs/ekip/PORTFOLIO-4.1-4.2-4.3-GEREKCE-2026-11-25.html)."""

from typing import Final

RISK_LEVELS: Final = ("LOW", "MEDIUM", "HIGH")          # also the IQ segments: the segment is the highest level a user may choose

# share of risky assets (%). Same steps as Yapi Kredi's published packages (fund share 20 / 50 / 80, October 2026)
RISKY_SHARE: Final = {"LOW": 20, "MEDIUM": 50, "HIGH": 80}

# 4.2: what the chosen assets take together (a product decision, not a measured number)
FOCUS_SHARE: Final = 60

SAFE_ASSETS: Final = ("TRY_DEPOSIT", "GOLD", "EUR")
RISKY_ASSETS: Final = ("SPX", "NVDA", "BIST", "BTC")
ASSETS: Final = SAFE_ASSETS + RISKY_ASSETS

# 4.3 risky part: split by inverse volatility. Yearly volatility (%) of daily closes, 2 January 2018 - 13 November 2026, USD
# (BTC Binance, S&P 500 HistData, NVDA Yahoo: adjusted for splits; BTC x sqrt(365), shares x sqrt(252)).
# An asset without a measurement is not in the standard basket (it can still be chosen in 4.2).
MEASURED_VOLATILITY: Final = {"SPX": 18.3, "NVDA": 50.2, "BTC": 64.7}

INSTITUTIONS: Final = ("ZIRAAT", "ISBANK", "YAPIKREDI")

# What the user sees. The code says whose published numbers they are; the name says what the numbers look like. "Protective / balanced /
# aggressive" was dropped: each institution publishes all three levels, and in the data the equity share does not follow those labels.
INSTITUTION_LABELS: Final = {
    "YAPIKREDI": ("Mevduat temelli paket", "Paranın bir kısmı vadeli mevduatta durur, kalanı fon sepetine gider; risk arttıkça fon payı artar."),
    "ISBANK": ("Çok varlıklı fon sepeti", "TL borçlanma, TL hisse, yabancı hisse, altın ve eurobond fonlarından oluşan sepet."),
    "ZIRAAT": ("Aktif yönetilen değişken fon", "Yöneticinin piyasaya göre ağırlık değiştirdiği değişken fonların dağılımı."),
}

# names for the screen (the AI service has its own table for sentences)
ASSET_LABELS: Final = {
    "TRY_DEPOSIT": "TL mevduat", "GOLD": "Altın", "EUR": "Euro", "SPX": "S&P 500", "NVDA": "Nvidia", "BIST": "BIST 100", "BTC": "Bitcoin",
    "TRY_BOND": "TL borçlanma ve faiz fonları", "TRY_EQUITY": "TL hisse", "FOREIGN_EQUITY": "Yabancı hisse", "CONSERVATIVE_FUND": "Temkinli değişken fon",
    "EUROBOND": "Eurobond", "EQUITY": "Hisse", "CASH_REPO": "Nakit ve ters repo", "OTHER_FUNDS": "Diğer fon payları (içeriği yayımlanmıyor)",
}

# 4.1: allocations the institutions themselves published, one per risk level. A snapshot: never updated silently.
INSTITUTION_BASKETS: Final = {
    # Yapi Kredi "Varlik Dagilim Onerileri", Ekim 2026: Temkinli 20 % ideal fund distribution + 80 % time deposit, Dengeli 50 + 50, Atak 80 + 20
    # (Dinamik 65 + 35 is between Dengeli and Atak and not used); ideal fund distribution: TL interest 50 (money market fund 40 + bond fund 10),
    # TL equity 20, gold 20, foreign (technology) equity 10. Checked against the PDF on 27 Nov 2026.
    "YAPIKREDI": {
        "LOW": {"TRY_DEPOSIT": 80, "TRY_BOND": 10, "TRY_EQUITY": 4, "GOLD": 4, "FOREIGN_EQUITY": 2},
        "MEDIUM": {"TRY_DEPOSIT": 50, "TRY_BOND": 25, "TRY_EQUITY": 10, "GOLD": 10, "FOREIGN_EQUITY": 5},
        "HIGH": {"TRY_DEPOSIT": 20, "TRY_BOND": 40, "TRY_EQUITY": 16, "GOLD": 16, "FOREIGN_EQUITY": 8},
    },
    "ISBANK": {             # Is Portfoy, model portfolios of the risk profile page
        "LOW": {"TRY_BOND": 70, "CONSERVATIVE_FUND": 30},
        "MEDIUM": {"TRY_BOND": 50, "TRY_EQUITY": 20, "FOREIGN_EQUITY": 15, "GOLD": 10, "EUROBOND": 5},
        "HIGH": {"TRY_BOND": 30, "TRY_EQUITY": 30, "FOREIGN_EQUITY": 25, "GOLD": 15},
    },
    # Ziraat Portfoy variable funds ZDD (Temkinli) / ZBD (Dengeli) / ZDZ (Agresif), "Fon Varlik Dagilimi" on their fund pages, values of the last business
    # day of October 2026 (read 27 Nov 2026; the pages change every month). Bonds = government + other bonds, cash/repo = cash collateral + reverse
    # repo. What "other funds" (katilma payi) hold is not published, so it is not guessed.
    "ZIRAAT": {
        "LOW": {"EQUITY": 7.24, "TRY_BOND": 43.32, "CASH_REPO": 4.48, "OTHER_FUNDS": 44.95},
        "MEDIUM": {"EQUITY": 29.73, "TRY_BOND": 20.38, "CASH_REPO": 1.38, "OTHER_FUNDS": 48.52},
        "HIGH": {"EQUITY": 81.13, "CASH_REPO": 5.06, "OTHER_FUNDS": 13.81},
    },
}

INSTITUTION_SOURCES: Final = {
    "YAPIKREDI": {"name": "Yapı Kredi, Varlık Dağılım Önerileri", "period": "2026-10", "url": "https://yapikredi.com.tr/medium/file/ekim_72960/view"},
    "ISBANK": {"name": "İş Portföy, risk profili sayfası", "period": "2026-11", "url": "https://www.isportfoy.com.tr/risk-profili-anketi"},
    "ZIRAAT": {"name": "Ziraat Portföy değişken fonları (ZDD, ZBD, ZDZ)", "period": "2026-10", "url": "https://www.ziraatportfoy.com.tr/zbd-ziraat-portfoy-dengeli-degisken-fon",
               # the fund of each risk level has its own page
               "urls": {"LOW": "https://www.ziraatportfoy.com.tr/zdd-ziraat-portfoy-temkinli-degisken-fon",
                        "MEDIUM": "https://www.ziraatportfoy.com.tr/zbd-ziraat-portfoy-dengeli-degisken-fon",
                        "HIGH": "https://www.ziraatportfoy.com.tr/zdz-ziraat-portfoy-agresif-degisken-fon"}},
}

DISCLAIMER: Final = "Yatırım tavsiyesi değildir. Dağılımlar bilgi ve demo amaçlıdır; kurumlarla bir bağlantımız yoktur."
