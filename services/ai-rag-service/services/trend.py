"""Capability 3, second half: the coach explains how the score moved over time (GET /ai/explain-iq-trend).

The IQ service keeps only score and segment per calculation (iq_history / fn_IqTrend), not the factors of each one.
So the cause of a past change is not known and is not invented: the trend is described from the history, and the
current strengths and weaknesses come from the latest result.
"""

from pydantic import ValidationError

from adapters.gateway import UserData
from adapters.llm import ChatModel
from core.domain import DISCLAIMER, SEGMENT_TR
from core.fmt import date_tr, num, parse_time
from core.number_check import allowed_from
from schemas.explain import FactorBreakdown
from schemas.insights import TrendResponse
from services.checked import Generated, generate_checked
from services.prompts import TREND_SYSTEM_PROMPT, data_block, iq_lines


def _change_words(change: int) -> str:
    if change > 0:
        return f"{change} puan artış"
    if change < 0:
        return f"{-change} puan düşüş"
    return "değişim yok"


def _direction(change: int) -> str:
    return "yükselişte" if change > 0 else "düşüşte" if change < 0 else "yatay"


def trend_lines(history: list[dict]) -> list[str]:
    points = sorted(history, key=lambda p: parse_time(p["calculatedAt"]))
    first, last = points[0], points[-1]
    scores = [int(p["score"]) for p in points]
    lines = [
        f"Hesaplama sayısı: {len(points)}",
        f"İlk hesaplama: {date_tr(parse_time(first['calculatedAt']))}, skor {first['score']}",
        f"Son hesaplama: {date_tr(parse_time(last['calculatedAt']))}, skor {last['score']}",
    ]
    if len(points) == 1:
        lines.append("Henüz tek hesaplama var; değişim yorumu yapılamaz")
        return lines

    total = scores[-1] - scores[0]
    lines += [
        f"İlk hesaplamadan bu yana: {_change_words(total)}",
        f"Son hesaplamada, öncekine göre: {_change_words(scores[-1] - scores[-2])}",
        f"En yüksek skor: {max(scores)}; en düşük skor: {min(scores)}",
    ]
    if last.get("movingAverage3") is not None:
        lines.append(f"Son üç hesaplamanın ortalaması: {num(float(last['movingAverage3']), 1)}")
    if first.get("segment") != last.get("segment"):
        lines.append(f"Segment değişti: {SEGMENT_TR.get(first['segment'], '?')} -> {SEGMENT_TR.get(last['segment'], '?')}")
    else:
        lines.append(f"Segment değişmedi: {SEGMENT_TR.get(last['segment'], '?')}")
    lines.append(f"Gidişat yorumu: skor genel olarak {_direction(total)}")
    return lines


def _current_lines(latest: dict | None) -> list[str]:
    if not latest:
        return []
    try:
        breakdown = FactorBreakdown.model_validate(latest.get("factorBreakdown") or {})
    except ValidationError:
        breakdown = None  # an unreadable or v1 breakdown: the trend alone is still worth explaining
    return ["Güncel durum:", *iq_lines(int(latest["score"]), latest["segment"], breakdown)]


def _template(lines: list[str]) -> str:
    # plain sentences from the same data block; every number in it comes from the history
    return "Skor geçmişinin özeti: " + "; ".join(l for l in lines if not l.startswith(("Güncel", "-", "Faktörler"))) + "."


def explain_trend(data: UserData, llm: ChatModel | None) -> TrendResponse:
    history = data.history()
    if not history:
        return TrendResponse(
            explanation="Henüz skor geçmişin yok; Finansal IQ'n hesaplandıkça gelişimini burada görebileceksin.",
            disclaimer=DISCLAIMER, numbers_verified=True, fallback_used=True, fallback_reason="NO_DATA", points=0,
        )

    history_part = trend_lines(history)
    lines = history_part + _current_lines(data.latest_iq())
    user = data_block(lines, "Skorunun zaman içindeki değişimini kullanıcıya açıkla.")
    generated: Generated = generate_checked(llm, TREND_SYSTEM_PROMPT, user, allowed_from(*lines),
                                            lambda: _template(history_part), max_sentences=6)
    return TrendResponse(
        explanation=generated.text, disclaimer=DISCLAIMER, model=generated.model, numbers_verified=True,
        fallback_used=generated.fallback_used, fallback_reason=generated.fallback_reason, points=len(history),
    )
