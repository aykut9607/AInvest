"""Turkish number formatting for everything a model or a user sees.

The number check parses text with the same conventions (12.500 = twelve thousand five hundred, 4,5 = four and a half),
so a value rendered here and copied by the model is recognised as the same number.
"""

import re
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal

_MONTHS = ["Ocak", "Şubat", "Mart", "Nisan", "Mayıs", "Haziran", "Temmuz", "Ağustos", "Eylül", "Ekim", "Kasım",
           "Aralık"]


def _round(value: float, decimals: int) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)


def num(value: float, decimals: int = 0) -> str:
    """12500 -> "12.500", 4.25 (1 decimal) -> "4,3", 3.0 (1 decimal) -> "3"."""
    rounded = _round(abs(value), decimals)
    whole, _, frac = f"{rounded:f}".partition(".")
    whole = f"{int(whole):,}".replace(",", ".")
    frac = frac.rstrip("0")
    sign = "-" if value < 0 and rounded != 0 else ""
    return sign + whole + ("," + frac if frac else "")


def tl(value: float) -> str:
    """Whole lira: 12500.4 -> "12.500 TL"."""
    return num(value) + " TL"


def pct(ratio: float) -> str:
    """0.184 -> "%18" (Turkish puts the sign first)."""
    return "%" + num(ratio * 100)


def date_tr(value: datetime) -> str:
    """Words, not 22.11.2026: a dotted date would be read as one odd number by the number check."""
    return f"{value.day} {_MONTHS[value.month - 1]} {value.year}"


_FRACTION = re.compile(r"(\.\d{6})\d+")


def parse_time(value: str | datetime) -> datetime:
    """ISO time from the .NET services: 7 fraction digits and no zone are common; a missing zone means UTC."""
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(_FRACTION.sub(r"\1", value.strip()).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
