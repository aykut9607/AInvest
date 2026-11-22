from fastapi import FastAPI

from api.routers import health

# Portfolio Service (:8084): the user's portfolio preferences and the deterministic allocation (4.1-4.3), and the
# 4.4 "AInvest view" module (rule-based confirmation score, backtested). Every number is computed here in code;
# the AI service only reads the result and explains it. Reached through the edge gateway (/api/portfolio/...),
# no CORS: browsers never call it directly.
# Skeleton (23 Nov 2026): health checks and the database connection only; the features come with their decisions.
app = FastAPI(title="AInvest Portfolio Service", version="0.1.0")

app.include_router(health.router)
