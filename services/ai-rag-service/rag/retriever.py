"""FAQ retrieval. Keyword overlap for now; the pgvector + HNSW retriever (Faz 3, RAG) will replace search()
with the same signature, so nothing that calls it changes."""

from core.text import stem, words
from rag.faq import FAQ, FaqEntry

# words that appear in nearly every question and would make everything match
_STOP = {"ben", "benim", "bana", "bir", "bu", "şu", "ne", "mi", "mı", "mu", "mü", "ve", "ile", "için", "nasıl",
         "neden", "kadar", "var", "yok", "olarak", "olan", "da", "de"}


def _stems(text: str) -> set[str]:
    return {stem(w) for w in words(text) if w not in _STOP and len(w) > 1}


_INDEX = [(entry, _stems(entry.question) | {stem(k) for k in entry.keywords}) for entry in FAQ]


def search(query: str, limit: int = 2) -> list[FaqEntry]:
    wanted = _stems(query)
    scored = [(len(wanted & terms), entry) for entry, terms in _INDEX]
    best = sorted((s for s in scored if s[0] > 0), key=lambda s: -s[0])
    return [entry for _, entry in best[:limit]]
