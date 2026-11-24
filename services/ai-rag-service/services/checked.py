"""The one pattern every generated text goes through: the model writes, code checks, the template is the B plan.

Checks, in order: empty answer, wrong script (language_check), numbers that are not in the data (number_check).
Whatever fails, the user gets the deterministic text and the reason is reported, never an error.

trace_checks() lets a caller see each check (what the model wrote, which numbers were not in the data). The service
does not use it; the evaluation playground does, to show a rejection live.
"""

import logging
import re
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Callable, Iterator

from adapters.llm import ChatModel, LlmUnavailable
from core.language_check import foreign_letters
from core.number_check import Allowed, verify_numbers
from schemas.common import FallbackReason

log = logging.getLogger("ai.checked")


@dataclass(frozen=True)
class Generated:
    text: str
    # model that wrote the text; None when the template was used
    model: str | None
    fallback_reason: FallbackReason | None

    @property
    def fallback_used(self) -> bool:
        return self.fallback_reason is not None


@dataclass(frozen=True)
class CheckRecord:
    model: str | None
    data: str  # what the model was given
    text: str  # what it wrote (after the sentence cap)
    reason: FallbackReason | None
    unknown_numbers: tuple[str, ...] = ()
    foreign: str = ""  # letters of another script, when that was the reason


_trace: ContextVar[list[CheckRecord] | None] = ContextVar("check_trace", default=None)


@contextmanager
def trace_checks() -> Iterator[list[CheckRecord]]:
    """Collects a CheckRecord for every check run inside the block (same thread / task)."""
    records: list[CheckRecord] = []
    token = _trace.set(records)
    try:
        yield records
    finally:
        _trace.reset(token)


def _inspect(text: str, allowed: Allowed) -> tuple[FallbackReason | None, tuple[str, ...], str]:
    if not text:
        log.warning("llm returned empty text")
        return "EMPTY_OUTPUT", (), ""
    foreign = foreign_letters(text)
    if foreign:
        # a few characters are enough to see which script it was; the text itself is not logged
        log.warning("llm output is not in Turkish script %s", foreign[:5])
        return "WRONG_LANGUAGE", (), "".join(foreign[:10])
    check = verify_numbers(text, allowed)
    if not check.verified:
        # only the offending numbers are logged, not the text
        log.warning("llm output has numbers not in the data %s", list(check.unknown))
        return "UNVERIFIED_NUMBERS", check.unknown, ""
    return None, (), ""


def rejection(text: str, allowed: Allowed, model: str | None = None, data: str = "") -> FallbackReason | None:
    """Why the model's text cannot be shown, or None when it passes every check."""
    reason, unknown, foreign = _inspect(text, allowed)
    records = _trace.get()
    if records is not None:
        records.append(CheckRecord(model, data, text, reason, unknown, foreign))
    return reason


# end of a sentence: . ! ? followed by whitespace; "1.740 TL" and "1,4 ay" have no space after the dot / comma
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


def cap_sentences(text: str, max_sentences: int) -> str:
    """Keeps at most max_sentences: the first ones and the last. The prompts ask for the advice in the last sentence,
    so cutting the tail would drop exactly that. Measured need: gemma3:4b went over six sentences in 2 to 5 of 30
    coach explanations, with or without worked examples in the prompt."""
    sentences = [s for s in _SENTENCE_END.split(" ".join(text.split())) if s]
    if len(sentences) <= max_sentences:
        return text
    log.info("llm output capped from %d to %d sentences", len(sentences), max_sentences)
    return " ".join(sentences[: max_sentences - 1] + sentences[-1:])


def generate_checked(llm: ChatModel | None, system: str, user: str, allowed: Allowed,
                     fallback: Callable[[], str], max_sentences: int | None = None) -> Generated:
    if llm is None:
        return Generated(fallback(), None, "LLM_UNAVAILABLE")
    try:
        text = llm.chat(system, user).strip()
    except LlmUnavailable as error:
        log.warning("llm unavailable, using template: %s", error)
        return Generated(fallback(), None, "LLM_UNAVAILABLE")
    if max_sentences:
        # cutting can only remove numbers, so the checks below still see everything that will be shown
        text = cap_sentences(text, max_sentences)
    reason = rejection(text, allowed, llm.model, user)
    if reason:
        return Generated(fallback(), None, reason)
    return Generated(text, llm.model, None)
