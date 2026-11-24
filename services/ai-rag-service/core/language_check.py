"""Catches answers that drift out of Turkish into another script (seen with Qwen 2.5 14B: whole answers in Chinese).

Allow-list, not block-list: every letter must be Latin (Basic Latin, Latin-1 Supplement, Latin Extended-A/B),
which covers Turkish including â, î, û. Chinese, Japanese, Cyrillic, Greek, Arabic and the rest are rejected.
Digits, punctuation and symbols are not letters and are left to the number check.

Known limit: a Latin-script answer in another language (e.g. English) passes.
"""

import unicodedata

_LATIN_END = 0x024F  # last code point of Latin Extended-B


def foreign_letters(text: str) -> list[str]:
    """Distinct non-Latin letters in the text, in order of appearance (empty when the text is Latin-only)."""
    seen: dict[str, None] = {}
    for ch in text:
        if ord(ch) > _LATIN_END and unicodedata.category(ch).startswith("L"):
            seen.setdefault(ch)
    return list(seen)
