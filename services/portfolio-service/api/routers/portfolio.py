import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from adapters.upstream import IqResult, MissingData, Upstream, UpstreamError, get_upstream
from api.deps import current_user_id
from db.models import PortfolioPreference, PortfolioProposal
from db.session import get_session
from schemas.envelope import Envelope
from schemas.portfolio import AllocationOut, BasedOn, InvestableOut, NamedCode, Options, Preferences, Proposal, RiskOut, Source, StyleInfo
from services import allocation
from services.baskets import ASSET_LABELS, ASSETS, DISCLAIMER, INSTITUTION_LABELS, INSTITUTION_SOURCES, INSTITUTIONS

router = APIRouter(prefix="/api/portfolio/{user_id}", tags=["portfolio"])

OPTIONS = ["INSTITUTION", "CUSTOM", "STANDARD", "AINVEST"]
NOT_READY = ["AINVEST"]          # 4.4: shown as "being prepared"


def owner(user_id: str, caller: Annotated[str, Depends(current_user_id)]) -> str:
    """The gateway already refuses other people's ids (sameUser); checked here too because the id decides whose data is read."""
    if user_id != caller:
        raise HTTPException(status_code=403, detail="Not your portfolio.")
    return user_id


Owner = Annotated[str, Depends(owner)]
Data = Annotated[Upstream, Depends(get_upstream)]
Db = Annotated[Session, Depends(get_session)]


def failure(error: Exception) -> JSONResponse:
    status = 404 if isinstance(error, MissingData) else 502 if isinstance(error, UpstreamError) else 400
    return JSONResponse(Envelope[None].error(str(error)).model_dump(), status_code=status)


def basket_for(p: Preferences) -> allocation.Basket:
    if p.focus_assets and p.option != "CUSTOM" or p.excluded_assets and p.option == "INSTITUTION" or p.institution_style and p.option != "INSTITUTION":
        raise allocation.AllocationError(f"A field that does not belong to {p.option} was sent.")          # never ignored silently
    if p.option == "INSTITUTION":
        return allocation.institution(p.institution_style, p.risk_level)
    if p.option == "CUSTOM":
        return allocation.custom(p.risk_level, tuple(dict.fromkeys(p.focus_assets)), tuple(dict.fromkeys(p.excluded_assets)))
    return allocation.standard(p.risk_level, tuple(dict.fromkeys(p.excluded_assets)))


def based_on(iq: IqResult) -> BasedOn:
    return BasedOn(iq_score=iq.score, segment=iq.segment, applied_rule=iq.applied_rule, iq_calculated_at=iq.calculated_at, scoring_version=iq.scoring_version, result_version=iq.result_version)


def money(i: allocation.Investable) -> InvestableOut:
    return InvestableOut(share_percent=i.share_percent, monthly_amount=i.monthly_amount, one_time_amount=i.one_time_amount)


@router.get("/options", response_model=Envelope[Options])
def options(user_id: Owner, upstream: Data):
    try:
        iq, profile = upstream.iq(user_id), upstream.profile(user_id)
    except (MissingData, UpstreamError) as error:
        return failure(error)
    i = allocation.investable(iq.score, iq.applied_rule, profile)
    return Envelope[Options].ok(Options(iq_score=iq.score, segment=iq.segment, max_risk=iq.segment, investable=money(i), options=OPTIONS, unavailable_options=NOT_READY,
                                        institution_styles=list(INSTITUTIONS),
                                        institution_style_info=[StyleInfo(code=c, label=INSTITUTION_LABELS[c][0], description=INSTITUTION_LABELS[c][1], source=Source(**INSTITUTION_SOURCES[c])) for c in INSTITUTIONS],
                                        assets=list(ASSETS), asset_info=[NamedCode(code=a, label=ASSET_LABELS[a]) for a in ASSETS], reasons=list(i.reasons)), "Options loaded.")


@router.get("/preferences", response_model=Envelope[Preferences])
def read_preferences(user_id: Owner, db: Db):
    row = db.get(PortfolioPreference, user_id)
    if row is None:
        return failure(MissingData("No portfolio choice yet."))
    return Envelope[Preferences].ok(Preferences.model_validate(row.choice), "Preferences loaded.")


@router.put("/preferences", response_model=Envelope[Preferences])
def save_preferences(user_id: Owner, body: Preferences, upstream: Data, db: Db):
    try:
        allocation.check_risk(body.risk_level, upstream.iq(user_id).segment)
        if body.option not in NOT_READY:
            basket_for(body)          # refuse an impossible choice before storing it
    except (MissingData, UpstreamError, allocation.AllocationError) as error:
        return failure(error)
    db.merge(PortfolioPreference(user_id=user_id, choice=body.model_dump(by_alias=True)))
    db.commit()
    return Envelope[Preferences].ok(body, "Preferences saved.")


@router.post("/proposal", response_model=Envelope[Proposal])
def create_proposal(user_id: Owner, upstream: Data, db: Db):
    row = db.get(PortfolioPreference, user_id)
    if row is None:
        return failure(MissingData("No portfolio choice yet."))
    choice = Preferences.model_validate(row.choice)
    if choice.option in NOT_READY:
        return JSONResponse(Envelope[None].error("The AInvest view is being prepared.").model_dump(), status_code=409)
    try:
        iq, profile = upstream.iq(user_id), upstream.profile(user_id)
        allocation.check_risk(choice.risk_level, iq.segment)          # the score may have fallen since the choice was saved
        basket = basket_for(choice)
    except (MissingData, UpstreamError, allocation.AllocationError) as error:
        return failure(error)
    i = allocation.investable(iq.score, iq.applied_rule, profile)
    percents = allocation.percentages(basket.weights)
    monthly, once = allocation.amounts(basket.weights, i.monthly_amount), allocation.amounts(basket.weights, i.one_time_amount)
    now = datetime.now(timezone.utc)
    proposal = Proposal(proposal_id=str(uuid.uuid4()), user_id=user_id, created_at=now.isoformat(), based_on=based_on(iq), preferences=choice,
                        risk=RiskOut(chosen=choice.risk_level, max_allowed=iq.segment), investable=money(i),
                        allocations=[AllocationOut(asset=a, label=ASSET_LABELS[a], percent=p, amount=monthly[a], one_time_amount=once[a]) for a, p in percents.items()],
                        reasons=[*i.reasons, *basket.reasons], source=Source(**basket.source) if basket.source else None, disclaimer=DISCLAIMER)
    db.add(PortfolioProposal(id=proposal.proposal_id, user_id=user_id, created_at=now, payload=proposal.model_dump(by_alias=True)))
    db.commit()
    return Envelope[Proposal].ok(proposal, "Proposal calculated.")


@router.get("/latest", response_model=Envelope[Proposal])
def latest(user_id: Owner, upstream: Data, db: Db):
    row = db.scalars(select(PortfolioProposal).where(PortfolioProposal.user_id == user_id).order_by(PortfolioProposal.created_at.desc()).limit(1)).first()
    if row is None:
        return failure(MissingData("No proposal yet."))
    proposal = Proposal.model_validate(row.payload)
    try:
        proposal.stale = upstream.iq(user_id).result_version != proposal.based_on.result_version
    except (MissingData, UpstreamError):
        return failure(UpstreamError("Financial IQ service is unavailable."))          # without it nobody knows whether the numbers are old
    return Envelope[Proposal].ok(proposal, "Latest proposal loaded.")
