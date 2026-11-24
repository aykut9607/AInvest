"""AInvest AI / RAG service (FastAPI, :8001). Faz 3; CLAUDE.md section 8.

Endpoints (all under the gateway's /ai route):
  POST /ai/explain-financial-iq   coach: why the IQ is what it is              (body: score, segment, factorBreakdown)
  POST /ai/assistant/ask          assistant: questions about the user's data   (router or tools mode)
  GET  /ai/insights/warnings      rule-based alerts from the profile and the IQ history
  GET  /ai/explain-iq-trend       coach: how the score moved over time
  GET  /ai/explain-portfolio      coach: the Portfolio Service's proposal       (sample data until the service exists)
"""

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from adapters.gateway import GatewayDenied, GatewayUnavailable
from api.routers import assistant, explain, insights
from core.config import get_settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="AInvest AI / RAG Service")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# the error body every AInvest service uses: { "message": ... } (validation errors keep FastAPI's 422 body)
@app.exception_handler(HTTPException)
def http_error(_: Request, error: HTTPException) -> JSONResponse:
    return JSONResponse(status_code=error.status_code, content={"message": error.detail})


@app.exception_handler(GatewayDenied)
def gateway_denied(_: Request, error: GatewayDenied) -> JSONResponse:
    status = 403 if str(error) == "403" else 401
    return JSONResponse(status_code=status, content={"message": "The gateway refused the token for this data."})


@app.exception_handler(GatewayUnavailable)
def gateway_unavailable(_: Request, error: GatewayUnavailable) -> JSONResponse:
    # a service behind the gateway is down: 502, like Finance does when IQ is down
    return JSONResponse(status_code=502, content={"message": "User data is unavailable right now."})


@app.get("/health")
def health():
    settings = get_settings()
    return {
        "service": "AI / RAG Service",
        "status": "Healthy",
        "llm": settings.ollama_model if settings.llm_enabled else "disabled (templates only)",
        "assistantMode": settings.assistant_mode,
        "toolsModel": settings.assistant_tools_model,
        "portfolioSource": settings.portfolio_source,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


app.include_router(explain.router)
app.include_router(assistant.router)
app.include_router(insights.router)
