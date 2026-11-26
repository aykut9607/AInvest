from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from core.domain import FACTORS, RULES, WARNINGS
from schemas.common import Camel, CheckedText, Level


class Adjustment(Camel):
    """Scoring v2.1: a floor or cap moved the score away from the sum of the factors (the factors are left as they are)."""

    rule: Literal["WEALTH_FLOOR", "INCOME_FLOOR", "DEBT_CAP"]
    from_factors: int = Field(ge=0, le=100)
    score: int = Field(ge=0, le=100)


class FactorBreakdown(Camel):
    """The factorBreakdown object of the Financial IQ service, contract v2. Unknown extra fields are ignored."""

    version: str | None = None
    factors: dict[str, float]
    warnings: list[str] = Field(default_factory=list)
    # set by the IQ service when a rule decided the score instead of the 5 factors
    applied_rule: Literal["VERY_HIGH_INCOME", "VERY_HIGH_WEALTH", "EXTREME_DEBT"] | None = None
    # v2.1, optional: set when a floor or cap changed the sum of the factors; never together with applied_rule
    adjustment: Adjustment | None = None

    @field_validator("factors")
    @classmethod
    def all_known_factors_in_range(cls, factors: dict[str, float]) -> dict[str, float]:
        # the contract requires all five; a v1 breakdown (RiskAlignment, 20-point maximums) is rejected here
        unknown = set(factors) - set(FACTORS)
        if unknown:
            raise ValueError(f"unknown factor: {', '.join(sorted(unknown))}")
        missing = set(FACTORS) - set(factors)
        if missing:
            raise ValueError(f"missing factor: {', '.join(sorted(missing))}")
        for key, points in factors.items():
            maximum = FACTORS[key][1]
            if not 0 <= points <= maximum:
                raise ValueError(f"{key} must be between 0 and {maximum}")
        return factors

    @field_validator("warnings")
    @classmethod
    def only_known_warnings(cls, warnings: list[str]) -> list[str]:
        # silently drop anything we do not know: free text from a client must never reach the prompt
        return [w for w in dict.fromkeys(warnings) if w in WARNINGS]


class ExplainRequest(Camel):
    """Input of /ai/explain-financial-iq. Only the IQ result: no name, e-mail or raw amounts (data minimisation)."""

    score: int = Field(ge=0, le=100)
    segment: Level
    # optional so clients that send only score + segment keep working (they get the template explanation)
    factor_breakdown: FactorBreakdown | None = None

    @field_validator("factor_breakdown", mode="before")
    @classmethod
    def empty_breakdown_is_no_breakdown(cls, value: Any) -> Any:
        # the IQ service returns {} for a breakdown it cannot read; that is "nothing to explain", not an error
        return None if value == {} else value

    @model_validator(mode="after")
    def breakdown_matches_score(self) -> "ExplainRequest":
        # the IQ score is the plain sum of the factor points, also when a rule decided it (the factors are then written
        # at their maximum or 0); a mismatch means the data was altered on the way
        b = self.factor_breakdown
        if b is None:
            return self
        total = sum(b.factors.values())
        if b.adjustment:
            # v2.1: the factors add up to fromFactors, the adjustment sets the score
            if b.applied_rule:
                raise ValueError("a breakdown has either an applied rule or an adjustment, not both")
            if int(total) != b.adjustment.from_factors:
                raise ValueError(f"factor points add up to {total:g}, not to fromFactors {b.adjustment.from_factors}")
            if b.adjustment.score != self.score:
                raise ValueError(f"{b.adjustment.rule} sets the score to {b.adjustment.score}, not {self.score}")
            return self
        if int(total) != self.score:
            raise ValueError(f"factor points add up to {total:g}, not to the score {self.score}")
        if b.applied_rule and RULES[b.applied_rule][0] != self.score:
            raise ValueError(f"{b.applied_rule} sets the score to {RULES[b.applied_rule][0]}, not {self.score}")
        return self


class ExplainResponse(CheckedText):
    explanation: str
    persona: Literal["coach"] = "coach"
