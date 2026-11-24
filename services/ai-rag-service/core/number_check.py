"""Output filter for the rule "the language model never computes numbers".

Every number the model may write comes from a data block that code built (score, amounts, ratios, dates). The allowed
set is taken from that block with the same parser, so a number the model copies passes and a number it invents or
computes fails; the deterministic template is shown instead. This is evaluation criterion (c) of the report,
enforced at runtime.

Why so strict: a check that merely asks "does this number exist somewhere in the data" missed a model writing 20/20
for a factor that had 15/15 (20 was another factor's value). That is why the coach explanation is not shown factor
points at all, and why percentages only pass when the data block contains that exact percentage.

Known limit: numbers written as words ("yirmi", "on iki bin") are not detected; the prompts ask for digits.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

# "1. ", "2) " at the start of a line are list markers, not claims about the data
_LIST_MARKER = re.compile(r"(?m)^\s*\d+[.)]\s+")
# a number, optionally with a Turkish "%20" prefix or "20%" suffix
_NUMBER = re.compile(r"(%\s*)?(\d+(?:[.,]\d+)*)(\s*%)?")
_THOUSANDS = re.compile(r"^\d{1,3}(\.\d{3})+$")


@dataclass(frozen=True)
class Allowed:
    """Numbers a text may contain: plain values and, separately, values that may appear as a percentage."""

    values: frozenset[Decimal] = field(default_factory=frozenset)
    percents: frozenset[Decimal] = field(default_factory=frozenset)

    def __or__(self, other: "Allowed") -> "Allowed":
        return Allowed(self.values | other.values, self.percents | other.percents)


@dataclass(frozen=True)
class NumberCheck:
    verified: bool
    # numbers found in the text that are not allowed (as written, e.g. "%20", "35")
    unknown: tuple[str, ...]


def _to_decimal(token: str) -> Decimal | None:
    if "," in token:                      # Turkish decimal comma: 1.250,5 -> 1250.5
        token = token.replace(".", "").replace(",", ".")
    elif _THOUSANDS.match(token):         # 12.500 -> 12500
        token = token.replace(".", "")
    try:
        return Decimal(token).normalize()
    except InvalidOperation:
        return None


def _numbers(text: str):
    for match in _NUMBER.finditer(_LIST_MARKER.sub("", text)):
        prefix, token, suffix = match.groups()
        yield match.group(0).strip(), _to_decimal(token), bool(prefix or suffix)


def allowed_from(*texts: str) -> Allowed:
    """Everything a model may repeat from the data block(s) it was given."""
    values, percents = set(), set()
    for text in texts:
        for _, value, is_percent in _numbers(text):
            if value is not None:
                (percents if is_percent else values).add(value)
    return Allowed(frozenset(values), frozenset(percents))


def allowed_values(*numbers: float) -> Allowed:
    return Allowed(frozenset(Decimal(str(n)).normalize() for n in numbers))


def verify_numbers(text: str, allowed: Allowed) -> NumberCheck:
    unknown = [
        written for written, value, is_percent in _numbers(text)
        if value is None or value not in (allowed.percents if is_percent else allowed.values)
    ]
    return NumberCheck(verified=not unknown, unknown=tuple(unknown))
