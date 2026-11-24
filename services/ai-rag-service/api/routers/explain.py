from fastapi import APIRouter, Depends

from adapters.llm import ChatModel
from api.deps import get_chat_model
from schemas.explain import ExplainRequest, ExplainResponse
from services.explainer import explain

router = APIRouter(tags=["coach"])


# contract used by web and mobile: body { score, segment, factorBreakdown? }; unchanged by the move to ai-rag-service
@router.post("/ai/explain-financial-iq", response_model=ExplainResponse)
def explain_financial_iq(request: ExplainRequest, llm: ChatModel | None = Depends(get_chat_model)) -> ExplainResponse:
    # sync on purpose: FastAPI runs it in a worker thread, so a slow model does not block other requests
    return explain(request, llm)
