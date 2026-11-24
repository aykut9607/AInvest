from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

Level = Literal["LOW", "MEDIUM", "HIGH"]

# why the deterministic text was shown instead of the model's
FallbackReason = Literal[
    "NO_BREAKDOWN",        # explain: the client sent only score + segment
    "NO_DATA",             # the user has no profile / IQ result / history / proposal yet
    "DATA_UNAVAILABLE",    # the gateway or a service behind it did not answer
    "LLM_UNAVAILABLE",     # model disabled, unreachable or erroring
    "EMPTY_OUTPUT",
    "WRONG_LANGUAGE",      # the answer left the Turkish script (seen with Qwen 2.5 14B: whole answers in Chinese)
    "UNVERIFIED_NUMBERS",  # the answer contains a number that is not in the data block
    "BLOCKED_INPUT",       # the question looked like a prompt injection
    "UNSUPPORTED",         # the question needs data the platform does not have yet (e.g. market prices)
]


class Camel(BaseModel):
    # JSON uses camelCase like the .NET and mobile code (factorBreakdown, fallbackUsed), Python uses snake_case
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class CheckedText(Camel):
    """Common part of every response with generated text: what was shown and whether the model's text survived."""

    disclaimer: str
    # model that wrote the text, None when the deterministic template was used
    model: str | None = None
    # true when every number in the text also appears in the data the text was built from
    numbers_verified: bool
    fallback_used: bool
    fallback_reason: FallbackReason | None = None
