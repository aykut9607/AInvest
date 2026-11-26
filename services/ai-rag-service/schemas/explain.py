from typing import Any, Literal

from pydantic import Field, field_validator, model_validator

from core.domain import (
    DEFAULT_SCORING_VERSION,
    FACTORS_BY_VERSION,
    MAX_SCORE,
    RULES,
    RULES_BY_VERSION,
    WARNINGS_BY_VERSION,
    rule_sets_score,
)
from schemas.common import Camel, CheckedText, Level


class FactorBreakdown(Camel):
    """The factorBreakdown object of the Financial IQ service, scoring v2 or v3. Unknown extra fields are ignored.

    The version decides which factors, maximums, warnings and rule labels are valid: "v2" or no version -> v2,
    "v3" -> v3 (variant v3c-i5). Anything else is rejected rather than guessed."""

    version: Literal["v2", "v3"] | None = None
    factors: dict[str, float]
    # v3: the maximum of each factor, sent next to the points so clients need no table of their own (optional)
    factor_maximums: dict[str, int] | None = None
    warnings: list[str] = Field(default_factory=list)
    # v2: a rule decided the score instead of the 5 factors; v3: a label for what moved the factors (sets nothing)
    applied_rule: Literal["VERY_HIGH_INCOME", "VERY_HIGH_WEALTH", "EXTREME_DEBT",
                          "SOLVENCY_CAP", "WEALTH_RUNWAY"] | None = None

    @property
    def scoring_version(self) -> str:
        return self.version or DEFAULT_SCORING_VERSION

    def maximums(self) -> dict[str, int]:
        """Factor maximums in display order: the breakdown's own when it sent them (validated below), else the table."""
        table = FACTORS_BY_VERSION[self.scoring_version]
        own = self.factor_maximums or {}
        return {key: own.get(key, maximum) for key, (_, maximum) in table.items()}

    def factor_rows(self) -> list[tuple[str, str, float, int]]:
        """(key, Turkish label, points, maximum) for every factor, in the version's order."""
        table = FACTORS_BY_VERSION[self.scoring_version]
        maxima = self.maximums()
        return [(key, label, self.factors[key], maxima[key]) for key, (label, _) in table.items()]

    @property
    def rule_sets_score(self) -> bool:
        return rule_sets_score(self.applied_rule)

    @field_validator("warnings")
    @classmethod
    def no_duplicate_warnings(cls, warnings: list[str]) -> list[str]:
        return list(dict.fromkeys(warnings))

    @model_validator(mode="after")
    def matches_its_version(self) -> "FactorBreakdown":
        version = self.scoring_version
        table = FACTORS_BY_VERSION[version]

        # the contract requires all five factors of the version; a v1 breakdown (RiskAlignment, 20-point maximums),
        # or v3 factors under a v2 label (and the other way round), is rejected here
        unknown = set(self.factors) - set(table)
        if unknown:
            raise ValueError(f"unknown factor for scoring {version}: {', '.join(sorted(unknown))}")
        missing = set(table) - set(self.factors)
        if missing:
            raise ValueError(f"missing factor for scoring {version}: {', '.join(sorted(missing))}")

        if self.factor_maximums is not None:
            maxima = self.factor_maximums
            if set(maxima) != set(table):
                raise ValueError(f"factorMaximums must name exactly the factors of scoring {version}")
            if any(m <= 0 for m in maxima.values()) or sum(maxima.values()) != MAX_SCORE:
                raise ValueError(f"factorMaximums must be positive and add up to {MAX_SCORE}")
            # v2 is frozen: other maximums under a v2 label mean the data was altered on the way
            if version == "v2" and any(maxima[k] != m for k, (_, m) in table.items()):
                raise ValueError("factorMaximums do not match scoring v2")

        for key, maximum in self.maximums().items():
            if not 0 <= self.factors[key] <= maximum:
                raise ValueError(f"{key} must be between 0 and {maximum}")

        if self.applied_rule and self.applied_rule not in RULES_BY_VERSION[version]:
            raise ValueError(f"{self.applied_rule} is not a rule of scoring {version}")

        # silently drop anything this version cannot produce: free text from a client must never reach the prompt
        self.warnings = [w for w in self.warnings if w in WARNINGS_BY_VERSION[version]]
        return self


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
        # the IQ score is the plain sum of the factor points in both versions, also when a v2 rule decided it (the
        # factors are then written at their maximum or 0); a mismatch means the data was altered on the way
        b = self.factor_breakdown
        if b is None:
            return self
        total = sum(b.factors.values())
        if int(total) != self.score:
            raise ValueError(f"factor points add up to {total:g}, not to the score {self.score}")
        # only the v2 rules force a score; the v3 labels (SOLVENCY_CAP, WEALTH_RUNWAY) are explanations
        if b.rule_sets_score and RULES[b.applied_rule][0] != self.score:
            raise ValueError(f"{b.applied_rule} sets the score to {RULES[b.applied_rule][0]}, not {self.score}")
        return self


class ExplainResponse(CheckedText):
    explanation: str
    persona: Literal["coach"] = "coach"
