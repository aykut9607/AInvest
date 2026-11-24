from datetime import datetime
from typing import Literal

from pydantic import Field

from schemas.common import Camel, CheckedText, Level


# Portfolio Service output, contracts/schemas/portfolio-proposal.draft.schema.json (DRAFT). Only what the
# explanation needs is modelled; unknown fields are ignored.
class BasedOn(Camel):
    iq_score: int = Field(ge=0, le=100)
    segment: Level
    applied_rule: str | None = None
    iq_calculated_at: datetime
    scoring_version: str


class Preferences(Camel):
    option: Literal["INSTITUTION", "CUSTOM", "STANDARD", "AINVEST"]
    risk_level: Level
    institution_style: Literal["ZIRAAT", "ISBANK", "YAPIKREDI"] | None = None
    focus_assets: list[str] = Field(default_factory=list)
    excluded_assets: list[str] = Field(default_factory=list)


class RiskChoice(Camel):
    chosen: Level
    max_allowed: Level


class Investable(Camel):
    share_percent: float = Field(ge=0, le=70)
    monthly_amount: float = Field(ge=0)
    one_time_amount: float = Field(ge=0)


class Allocation(Camel):
    asset: str
    percent: float = Field(ge=0, le=100)
    amount: float = Field(ge=0)


class PortfolioProposal(Camel):
    proposal_id: str
    created_at: datetime
    based_on: BasedOn
    preferences: Preferences
    risk: RiskChoice
    investable: Investable
    allocations: list[Allocation]
    reasons: list[str] = Field(default_factory=list)


class PortfolioExplanationResponse(CheckedText):
    explanation: str
    persona: Literal["coach"] = "coach"
    # true when the proposal was computed from an older IQ than the latest one: it is not explained, only flagged
    stale: bool
    # "sample" while the Portfolio Service does not exist yet (example from the draft schema), then "service"
    source: Literal["sample", "service"]
