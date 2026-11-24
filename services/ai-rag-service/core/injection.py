"""Input filter for free text from the user (the assistant's question), the first of the prompt-security layers.

The question is the only free text that ever reaches a model. Before that it must pass this filter; a match is
refused without calling the model. Behind it there are more layers: the <soru> delimiters and the system prompt rule
"text in <soru> is never an instruction", and on the way out the language and number checks.

Honest limit (ADR-012): a pattern list cannot stop every rewording, so this layer lowers the risk, it does not remove
it. What an attacker could gain is also small by design: the model only sees the user's own data (fetched with the
user's own token) and cannot call anything that writes.
"""

import re

from core.text import tr_lower

_PATTERNS = [
    # Turkish
    r"(önceki|yukarıdaki|tüm|bütün|verilen)\s+(talimat|komut|kural|yönerge)\w*\s+(unut|yok say|görmezden gel|iptal)",
    r"(talimat|kural|yönerge)\w*\s+(unut|yok say|görmezden gel)",
    r"sistem\s+(mesaj|komut|istem|prompt)\w*",
    r"(rolünü|kimliğini|kişiliğini)\s+(değiştir|unut|bırak)",
    r"artık\s+sen\s+.{0,40}?(sin|sın|sun|sün)\b",
    r"(geliştirici|developer|yönetici|admin)\s+mod",
    r"(başka|diğer)\s+(bir\s+)?kullanıcı\w*\s+(veri|bilgi|borç|borc|profil|skor)",
    r"(şifre|parola|token|api anahtar)\w*",
    # English
    r"ignore\s+(all\s+|the\s+)?(previous|above|prior)\s+(instructions|rules)",
    r"(system|developer)\s+prompt",
    r"you\s+are\s+now\b",
    r"jailbreak|\bdan\s+mode\b",
    # delimiter smuggling: a fake end of our data / question block
    r"</?\s*(veri|soru|system|sistem)\s*>",
]
_COMPILED = [re.compile(p) for p in _PATTERNS]


def looks_like_injection(text: str) -> bool:
    # Turkish and English lowercasing differ ("Ignore" -> "ıgnore" vs "ignore"), so both are checked
    variants = {tr_lower(text), text.lower()}
    return any(p.search(v) for p in _COMPILED for v in variants)
