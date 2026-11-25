from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from api.routers import health, market, portfolio
from schemas.envelope import Envelope

# Portfolio Service (:8084): the user's portfolio preferences and the deterministic allocation (4.1-4.3), and the
# 4.4 "AInvest view" module (rule-based confirmation score, backtested). Every number is computed here in code;
# the AI service only reads the result and explains it. Reached through the edge gateway (/api/portfolio/...),
# no CORS: browsers never call it directly.
app = FastAPI(title="AInvest Portfolio Service", version="0.2.0")


@app.exception_handler(HTTPException)
def refused(request: Request, error: HTTPException) -> JSONResponse:
    """Every error has the same envelope as the answers, so the screens read one shape."""
    return JSONResponse(Envelope[None].error(str(error.detail)).model_dump(), status_code=error.status_code)


@app.exception_handler(RequestValidationError)
def unreadable(request: Request, error: RequestValidationError) -> JSONResponse:
    first = error.errors()[0]
    return JSONResponse(Envelope[None].error(f"{'.'.join(str(x) for x in first['loc'][1:]) or 'body'}: {first['msg']}").model_dump(), status_code=400)


app.include_router(health.router)
app.include_router(market.router)
app.include_router(portfolio.router)
