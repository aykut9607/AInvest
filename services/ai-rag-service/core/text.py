import re

_WORD = re.compile(r"[a-zçğıöşüâîû0-9]+")


def tr_lower(text: str) -> str:
    """str.lower() is wrong for Turkish: "I" must become "ı" and "İ" must become "i".
    "IQ" is a loanword and stays "iq" (otherwise "Finansal IQ" would become "ıq")."""
    return text.replace("IQ", "iq").replace("I", "ı").replace("İ", "i").lower()


def words(text: str) -> list[str]:
    return _WORD.findall(tr_lower(text))


def stem(word: str, length: int = 5) -> str:
    """Crude Turkish stem: the language is agglutinative, so "borcum", "borçlarım" and "borç" share a prefix.
    Good enough for keyword matching; not a linguistic stemmer."""
    return word[:length]
