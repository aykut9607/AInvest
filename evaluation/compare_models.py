"""Compares local models on the coach explanation, using the production AI-service code (prompt, number check, fallback).

    run evaluation/run_evaluation.py first (it writes out/clean.scored.json), then:
    services/ai-rag-service/venv/Scripts/python evaluation/compare_models.py
    ... --models gemma3:4b llama3.1:8b mistral:7b --per-segment 10
    ... --models claude-opus-5-5     # hosted reference; key in .env, pip install -r evaluation/requirements.txt

Each run adds to / replaces its models in out/model_comparison.json and out/model_outputs.md; other models stay.

Automatic metrics are deliberately simple and approximate; Turkish quality is left to the human reading
out/model_outputs.md.
"""

import argparse
import json
import os
import random
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "services" / "ai-rag-service"))

from adapters.llm import OllamaChatModel  # noqa: E402
from core.config import get_settings  # noqa: E402
from core.domain import SEGMENT_TR  # noqa: E402
from schemas.explain import ExplainRequest  # noqa: E402
from services.explainer import explain  # noqa: E402

OUT = HERE / "out"


def load_dotenv(path: Path = HERE.parent / ".env") -> None:
    """Reads KEY=value lines (API keys of the hosted reference models) from the git-ignored .env file.
    Variables already set in the environment win; values are never printed."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        key, sep, value = line.strip().partition("=")
        if sep and key and not key.startswith("#"):
            os.environ.setdefault(key.strip(), value.strip().strip("'\""))

# formal "siz" forms: words ending in -nız/-niz/-nuz/-nüz (skorunuz, durumunuz, almalısınız); a few common
# words that merely end like that are excluded. Approximate on purpose.
_SIZ = re.compile(r"\b(siz|sizin|size|sizi|\w+n[ıiuü]z)\b", re.IGNORECASE)
_NOT_SIZ = {"yalnız", "deniz", "biz", "bizim", "hiç", "temiz", "henüz"}
_SEGMENT_PHRASE = re.compile(r"\b(düşük|orta|yüksek)\s+segment", re.IGNORECASE)
_SENTENCE_END = re.compile(r"[.!?](\s|$)")


def sample(scored: list[dict], per_segment: int, seed: int) -> list[dict]:
    rng = random.Random(seed)
    picked = []
    for segment in ("LOW", "MEDIUM", "HIGH"):
        pool = [r for r in scored if r["segment"] == segment]
        picked += rng.sample(pool, min(per_segment, len(pool)))
    return picked


def text_checks(text: str, segment: str) -> dict:
    siz = [w for w in _SIZ.findall(text) if w.lower() not in _NOT_SIZ]
    named = {m.lower() for m in _SEGMENT_PHRASE.findall(text)}
    return {
        "siz_used": bool(siz),
        "wrong_segment": bool(named - {SEGMENT_TR[segment].lower()}),
        "sentences": len(_SENTENCE_END.findall(text)),
        "paragraphs": len([p for p in text.split("\n\n") if p.strip()]),
    }


def make_model(model_name: str):
    """claude-* is the hosted reference model; anything else is a local Ollama model."""
    if model_name.startswith("claude-"):
        from hosted_models import AnthropicChatModel  # SDK only needed for this one
        return AnthropicChatModel(model_name)
    settings = get_settings()
    # first load from disk can take minutes for an 8B model; give the warm-up its own long timeout
    OllamaChatModel(settings.ollama_base_url, model_name, timeout_seconds=600).chat(
        "Merhaba", "Tek kelimeyle cevap ver: hazır mısın?")
    return OllamaChatModel(settings.ollama_base_url, model_name, settings.llm_timeout_seconds)


def run_model(model_name: str, items: list[dict]) -> tuple[dict, list[dict]]:
    model = make_model(model_name)

    rows, seconds = [], []
    for item in items:
        request = ExplainRequest.model_validate(item)
        started = time.perf_counter()
        response = explain(request, model)
        seconds.append(time.perf_counter() - started)
        checks = text_checks(response.explanation, request.segment) if not response.fallback_used else {}
        rows.append({"userId": item["userId"], "segment": request.segment,
                     "rule": request.factor_breakdown.applied_rule or "-",
                     "fallback": response.fallback_reason, "checks": checks, "text": response.explanation})

    answered = [r for r in rows if r["fallback"] is None]
    n = len(rows)

    def share(pred):
        return round(sum(pred(r) for r in answered) / len(answered), 3) if answered else None

    metrics = {
        "profiles": n,
        "fallback_rate": round((n - len(answered)) / n, 3),
        "fallback_reasons": {k: sum(r["fallback"] == k for r in rows) for k in {r["fallback"] for r in rows} if k},
        "of_model_answers": {
            "siz_used": share(lambda r: r["checks"]["siz_used"]),
            "wrong_segment_named": share(lambda r: r["checks"]["wrong_segment"]),
            "over_6_sentences": share(lambda r: r["checks"]["sentences"] > 6),
            "multi_paragraph": share(lambda r: r["checks"]["paragraphs"] > 1),
        },
        "seconds_mean": round(statistics.mean(seconds), 2),
        "seconds_p90": round(sorted(seconds)[int(0.9 * (n - 1))], 2),
    }
    if hasattr(model, "usage"):
        metrics["tokens"] = model.usage()  # hosted models: to report what the comparison cost
    return metrics, rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", default=["gemma3:4b", "llama3.1:8b", "mistral:7b"])
    ap.add_argument("--per-segment", type=int, default=10)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--tag", default="", help="stored as <model>+<tag>, e.g. base / fewshot (PROMPT_EXAMPLES)")
    args = ap.parse_args()
    load_dotenv()

    scored = json.loads((OUT / "clean.scored.json").read_text(encoding="utf-8"))
    items = sample(scored, args.per_segment, args.seed)
    scoring = ",".join(sorted({i["factorBreakdown"].get("version", "v1") for i in items}))

    # results of models run earlier (same sample, same scoring rules) are kept, so a single model can be added or
    # re-run alone. The v1 results (6 factors, incl. the Claude reference) are kept in model_comparison_v1.json
    summary_path, report_path = OUT / "model_comparison.json", OUT / "model_outputs.md"
    summary = json.loads(summary_path.read_text(encoding="utf-8")) if summary_path.exists() else {}
    previous = summary.get("parameters", {})
    if previous and (previous.get("per_segment"), previous.get("seed"), previous.get("scoring", "v1")) != (
            args.per_segment, args.seed, scoring):
        summary = {}  # different sample or scoring rules: earlier numbers are not comparable
    sections = {}
    if summary and report_path.exists():
        for chunk in report_path.read_text(encoding="utf-8").split("\n## ")[1:]:
            sections[chunk.split("\n", 1)[0].strip()] = "\n## " + chunk

    for name in args.models:
        print(f"running {name} on {len(items)} profiles...", flush=True)
        metrics, rows = run_model(name, items)
        metrics["promptExamples"] = get_settings().prompt_examples
        name = f"{name}+{args.tag}" if args.tag else name
        summary[name] = metrics
        print(json.dumps(metrics, ensure_ascii=False, indent=1), flush=True)
        section = [f"\n## {name}\n"]
        for r in rows:
            tag = f"TEMPLATE ({r['fallback']})" if r["fallback"] else "model"
            section.append(f"\n**{r['userId']}** | {r['segment']} | rule {r['rule']} | {tag}\n\n{r['text']}\n")
        sections[name] = "".join(section)

    models = [m for m in summary if m != "parameters"]
    summary["parameters"] = {**vars(args), "models": models, "scoring": scoring}
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text("# Model outputs\n" + "".join(sections[m] for m in models if m in sections), encoding="utf-8")


if __name__ == "__main__":
    main()
