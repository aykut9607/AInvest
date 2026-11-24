from typing import Literal

from pydantic import Field

from schemas.common import Camel, CheckedText

Severity = Literal["CRITICAL", "WARNING", "INFO"]


class Alert(Camel):
    # stable code for the apps (icon, colour, deep link); message is the Turkish text shown to the user
    code: str
    severity: Severity
    message: str


class WarningsResponse(Camel):
    """Rule-based, no language model: an alert must be exactly right every time."""

    alerts: list[Alert] = Field(default_factory=list)
    disclaimer: str


class TrendResponse(CheckedText):
    explanation: str
    persona: Literal["coach"] = "coach"
    # how many calculations the explanation is based on
    points: int
