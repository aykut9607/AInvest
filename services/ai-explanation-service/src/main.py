from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime, timezone

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
def health():
    return {
        "service": "AI Explanation Service",
        "status": "Healthy",
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

class ExplainRequest(BaseModel):
    score: int
    segment: str

class ExplainResponse(BaseModel):
    explanation: str
    disclaimer: str

@app.post("/ai/explain-financial-iq")
def explain(request: ExplainRequest):
    templates = {
        "STRONG": "Your financial standing looks strong, your cash reserve comfortably covers your expenses.",
        "BALANCED": "Your financial standing is balanced, there's room for improvement in some areas such as cash reserve or debt ratio.",
        "NEEDS_IMPROVEMENT": "Your cash reserve is low relative to your expenses, you might consider increasing your savings.",
        "HIGH_RISK": "Your financial standing needs attention, your debt ratio and cash reserve may be priority areas to review."
    }
    explanation = templates.get(request.segment, "Your score has been calculated. Consult your advisor for a detailed analysis.")
    return ExplainResponse(
        explanation=explanation,
        disclaimer="This information is for educational purposes only, not investment advice."
    )