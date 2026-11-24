from typing import Literal

from pydantic import Field

from schemas.common import Camel, CheckedText

AssistantMode = Literal["router", "tools"]


class AskRequest(Camel):
    question: str = Field(min_length=1, max_length=500)
    # optional override of ASSISTANT_MODE, used by the comparison of the two approaches
    mode: AssistantMode | None = None


class AskResponse(CheckedText):
    answer: str
    persona: Literal["assistant"] = "assistant"
    mode: AssistantMode
    # what the answer is about: the intents the router picked, or the tools the model called (as intents)
    intents: list[str] = Field(default_factory=list)
