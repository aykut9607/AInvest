from fastapi import APIRouter, Depends

from adapters.gateway import UserData
from adapters.llm import ChatModel
from api.deps import get_chat_model, get_user_data
from core.domain import DISCLAIMER
from schemas.insights import TrendResponse, WarningsResponse
from schemas.portfolio import PortfolioExplanationResponse
from services.alerts import alerts_for
from services.portfolio import explain_portfolio
from services.trend import explain_trend

router = APIRouter(tags=["insights"])


@router.get("/ai/insights/warnings", response_model=WarningsResponse)
def warnings(data: UserData = Depends(get_user_data)) -> WarningsResponse:
    # the latest IQ result decides the scoring version (and rule) whose thresholds the alerts use
    return WarningsResponse(alerts=alerts_for(data.profile(), data.history(), data.latest_iq()), disclaimer=DISCLAIMER)


@router.get("/ai/explain-iq-trend", response_model=TrendResponse)
def iq_trend(data: UserData = Depends(get_user_data), llm: ChatModel | None = Depends(get_chat_model)) -> TrendResponse:
    return explain_trend(data, llm)


@router.get("/ai/explain-portfolio", response_model=PortfolioExplanationResponse)
def portfolio(data: UserData = Depends(get_user_data),
              llm: ChatModel | None = Depends(get_chat_model)) -> PortfolioExplanationResponse:
    return explain_portfolio(data, llm)
