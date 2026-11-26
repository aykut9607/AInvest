"""Request and response shapes of /api/portfolio/{userId}/... (contracts/schemas/portfolio-proposal.draft.schema.json)."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

Option = Literal["INSTITUTION", "CUSTOM", "STANDARD", "AINVEST"]
Risk = Literal["LOW", "MEDIUM", "HIGH"]
Style = Literal["ZIRAAT", "ISBANK", "YAPIKREDI"]
AssetName = Annotated[str, Field(min_length=1, max_length=20)]


class Camel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class Preferences(Camel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True, extra="forbid")

    option: Option
    risk_level: Risk
    institution_style: Style | None = None
    focus_assets: list[AssetName] = Field(default_factory=list, max_length=10)
    excluded_assets: list[AssetName] = Field(default_factory=list, max_length=10)


class InvestableBasis(Camel):
    """Where the amounts come from (optional): surplus = income - expenses - installment; emergency fund = reserve_months x expenses;
    free cash = cash above that fund; reserve = cash + half of the investments (the IQ counts it the same way)."""
    monthly_income: float
    monthly_expenses: float
    monthly_debt_payment: float
    monthly_surplus: float
    cash_reserve: float
    investment_amount: float
    reserve: float
    emergency_fund: float
    free_cash: float
    reserve_months: int


class InvestableOut(Camel):
    share_percent: float
    monthly_amount: float
    one_time_amount: float
    basis: InvestableBasis | None = None          # optional, 27 Nov
    reasons: list[str] = []                       # RESERVE_FIRST, NO_MONTHLY_SURPLUS, DEBT_FIRST


class Source(Camel):
    name: str
    period: str          # month the numbers were published for
    url: str


class NamedCode(Camel):
    code: str
    label: str


class StyleInfo(NamedCode):
    description: str
    source: Source


class Options(Camel):
    iq_score: int
    segment: Risk
    max_risk: Risk
    investable: InvestableOut
    options: list[Option]
    unavailable_options: list[Option]          # shown but not selectable yet
    institution_styles: list[Style]
    institution_style_info: list[StyleInfo]          # names and sources for the screen
    assets: list[str]
    asset_info: list[NamedCode]
    reasons: list[str]


class BasedOn(Camel):
    iq_score: int
    segment: Risk
    applied_rule: str | None
    iq_calculated_at: str
    scoring_version: str
    result_version: int | None = None


class RiskOut(Camel):
    chosen: Risk
    max_allowed: Risk


class AllocationOut(Camel):
    asset: str
    label: str
    percent: float
    amount: float
    one_time_amount: float


class Proposal(Camel):
    proposal_id: str
    user_id: str
    created_at: str
    based_on: BasedOn
    preferences: Preferences
    risk: RiskOut
    investable: InvestableOut
    allocations: list[AllocationOut]
    reasons: list[str]
    source: Source | None = None          # only INSTITUTION: where the published percentages come from
    stale: bool = False                   # the IQ result changed after this proposal
    disclaimer: str
