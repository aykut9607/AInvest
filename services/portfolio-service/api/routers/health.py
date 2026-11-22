from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import Engine

from db.session import database_reachable, get_engine

router = APIRouter(prefix="/health", tags=["health"])

SERVICE_NAME = "portfolio-service"


@router.get("")
def health() -> dict:
    """Liveness: the process answers (same shape as the other services' /health)."""
    return {"service": SERVICE_NAME, "status": "Healthy", "timestamp": datetime.now(timezone.utc).isoformat()}


@router.get("/db-check")
def db_check(engine: Annotated[Engine, Depends(get_engine)]) -> JSONResponse:
    """Readiness: portfolio_db answers. Health endpoints are unauthenticated, so nothing but the status is returned."""
    if database_reachable(engine):
        return JSONResponse({"database": "reachable"})
    return JSONResponse({"database": "unreachable"}, status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
