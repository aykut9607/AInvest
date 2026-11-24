from fastapi import APIRouter, Depends

from adapters.gateway import UserData
from api.deps import get_chat_model, get_tools_model, get_user_data
from core.config import get_settings
from schemas.assistant import AskRequest, AskResponse
from services.assistant import ask

router = APIRouter(tags=["assistant"])


@router.post("/ai/assistant/ask", response_model=AskResponse)
def assistant_ask(
    request: AskRequest,
    data: UserData = Depends(get_user_data),
    router_llm=Depends(get_chat_model),
    tools_llm=Depends(get_tools_model),
) -> AskResponse:
    mode = request.mode or get_settings().assistant_mode
    return ask(request.question, "tools" if mode == "tools" else "router", data, router_llm, tools_llm)
