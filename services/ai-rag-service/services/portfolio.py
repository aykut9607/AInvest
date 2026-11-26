"""Capability 4 of the report: explain the portfolio proposal (GET /ai/explain-portfolio).

The allocation is computed by the Portfolio Service (Aykut, deterministic, no LLM; CLAUDE.md 8.4). The AI never
computes or changes it: it turns the proposal's numbers and reason codes into sentences, and the number check makes
sure every number it writes is one of the proposal's. A proposal computed from an older IQ than the latest one is not
explained at all, only flagged as stale.
"""

import re

from pydantic import ValidationError

from adapters.gateway import UserData
from adapters.llm import ChatModel
from core.domain import DISCLAIMER, LEVEL_TR, SEGMENT_TR, scoring_version_of
from core.fmt import date_tr, num, parse_time, tl
from core.number_check import allowed_from
from schemas.portfolio import PortfolioExplanationResponse, PortfolioProposal
from services.checked import Generated, generate_checked
from services.prompts import PORTFOLIO_SYSTEM_PROMPT, data_block

ASSETS_TR = {
    "GOLD": "Altın", "SILVER": "Gümüş", "TRY_DEPOSIT": "TL mevduat", "TRY_BOND": "TL tahvil", "BOND": "Tahvil",
    "SPX": "S&P 500 endeksi", "NDQ": "Nasdaq endeksi", "BIST": "BIST 100 endeksi", "BIST100": "BIST 100 endeksi",
    "EUR": "Euro", "USD": "Dolar", "NVDA": "Nvidia hissesi", "BTC": "Bitcoin", "ETH": "Ethereum", "OIL": "Petrol",
    "AI_STOCKS": "yapay zekâ şirketleri hisseleri",
}
OPTION_TR = {
    "INSTITUTION": "kurum tarzı portföy",
    "CUSTOM": "kendi seçtiğin alana odaklı portföy",
    "STANDARD": "standart dengeli sepet",
    "AINVEST": "AInvest önerisi (geçmiş verilerle test edilmiş kural tabanlı öneri)",
}
STYLE_TR = {"ZIRAAT": "koruyucu (Ziraat tarzı)", "ISBANK": "dengeli (İş Bankası tarzı)",
            "YAPIKREDI": "agresif (Yapı Kredi tarzı)"}

# asset codes come from our own service, but they still end up in a prompt: anything that is not a plain code is
# replaced instead of passed through
_CODE = re.compile(r"^[A-Z0-9_]{1,24}$")
_REPLACED = re.compile(r"^EXCLUDED_ASSET_REPLACED:([A-Z0-9_]{1,24})->([A-Z0-9_]{1,24})$")
_REASONS = {
    "IQ_TILT_TO_SAFE_ASSETS": "Finansal IQ'na göre dağılım daha güvenli varlıklara kaydırıldı.",
    "RESERVE_FIRST": "Acil durum fonun yeterli olmadığı için yatırılabilir tutar sınırlandı; önce fonu tamamlaman öngörüldü.",
    "RISK_CAPPED_BY_IQ": "Seçebileceğin risk seviyesi Finansal IQ'nla sınırlandı.",
}


def asset_name(code: str) -> str:
    if code in ASSETS_TR:
        return ASSETS_TR[code]
    return code if _CODE.match(code) else "Diğer varlık"


def reason_sentence(code: str) -> str | None:
    replaced = _REPLACED.match(code)
    if replaced:
        return f"İstemediğin {asset_name(replaced[1])} yerine {asset_name(replaced[2])} kondu."
    return _REASONS.get(code)  # unknown codes are dropped, never shown raw


def proposal_lines(p: PortfolioProposal) -> list[str]:
    option = OPTION_TR[p.preferences.option]
    if p.preferences.option == "INSTITUTION" and p.preferences.institution_style:
        option += f", {STYLE_TR[p.preferences.institution_style]}"
    lines = [
        f"Öneri türü: {option}",
        f"Dayandığı Finansal IQ: {p.based_on.iq_score} / 100 ({SEGMENT_TR[p.based_on.segment]} segment)",
        f"Risk seviyesi: seçtiğin {LEVEL_TR[p.risk.chosen]}; skorunun izin verdiği en yüksek seviye "
        f"{LEVEL_TR[p.risk.max_allowed]}",
        f"Yatırılabilir pay: %{num(p.investable.share_percent, 1)} (kural: Finansal IQ eksi 30, %0 ile %70 arasında)",
        f"Aylık yatırılabilir tutar (aylık artan paranın bu payı): {tl(p.investable.monthly_amount)}",
        f"Tek seferlik yatırılabilir tutar (3 aylık acil durum fonunun üstündeki nakdin bu payı): "
        f"{tl(p.investable.one_time_amount)}",
        "Dağılım:",
        *[f"- {asset_name(a.asset)}: %{num(a.percent, 1)}, aylık {tl(a.amount)}" for a in p.allocations],
    ]
    if p.preferences.excluded_assets:
        lines.append("İstemediğin varlıklar: " + ", ".join(asset_name(a) for a in p.preferences.excluded_assets))
    reasons = [s for s in (reason_sentence(r) for r in p.reasons) if s]
    if reasons:
        lines.append("Gerekçeler: " + " ".join(reasons))
    return lines


def _template(p: PortfolioProposal) -> str:
    parts = ", ".join(f"{asset_name(a.asset)} %{num(a.percent, 1)} (aylık {tl(a.amount)})" for a in p.allocations)
    text = (f"Bu {OPTION_TR[p.preferences.option]}, {p.based_on.iq_score} Finansal IQ skoruna göre hazırlandı. "
            f"Skoruna göre gelirinden yatırıma ayırabileceğin pay %{num(p.investable.share_percent, 1)}: "
            f"ayda {tl(p.investable.monthly_amount)} ve bir kerelik {tl(p.investable.one_time_amount)}. "
            f"Dağılım: {parts}.")
    reasons = [s for s in (reason_sentence(r) for r in p.reasons) if s]
    return text + (" " + " ".join(reasons) if reasons else "")


def _stale_since(p: PortfolioProposal, latest: dict | None) -> str | None:
    """Text for a proposal that was computed from an older IQ than the latest one, else None."""
    if not latest:
        return None
    newer = parse_time(latest["createdAt"]) > parse_time(p.based_on.iq_calculated_at)
    # a result rescored under other rules (v2 -> v3) may keep its createdAt and even its score
    same_rules = scoring_version_of(latest.get("factorBreakdown")) == p.based_on.scoring_version
    if not newer and int(latest["score"]) == p.based_on.iq_score and same_rules:
        return None
    return (f"Bu öneri {date_tr(parse_time(p.based_on.iq_calculated_at))} tarihli {p.based_on.iq_score} skoruna "
            f"dayanıyor; Finansal IQ'n o tarihten sonra {latest['score']} olarak yeniden hesaplandı. Güncel bir öneri "
            f"oluşturmadan bu dağılımı kullanma.")


def explain_portfolio(data: UserData, llm: ChatModel | None) -> PortfolioExplanationResponse:
    raw, source = data.portfolio()
    common = {"disclaimer": DISCLAIMER, "numbers_verified": True, "source": source}
    if not raw:
        return PortfolioExplanationResponse(
            explanation="Henüz bir portföy önerin yok; Finansal IQ'nu gördükten sonra bir seçenek ve risk seviyesi "
                        "seçerek öneri oluşturabilirsin.",
            fallback_used=True, fallback_reason="NO_DATA", stale=False, **common)
    try:
        proposal = PortfolioProposal.model_validate(raw)
    except ValidationError:
        return PortfolioExplanationResponse(
            explanation="Portföy önerin şu an okunamıyor; lütfen biraz sonra tekrar dene.",
            fallback_used=True, fallback_reason="DATA_UNAVAILABLE", stale=False, **common)

    # the sample belongs to a demo user, not to the caller: comparing it with the caller's IQ would be meaningless
    stale = _stale_since(proposal, data.latest_iq()) if source == "service" else None
    if stale:
        return PortfolioExplanationResponse(explanation=stale, fallback_used=False, stale=True, **common)

    lines = proposal_lines(proposal)
    user = data_block(lines, "Bu portföy önerisini kullanıcıya açıkla.")
    generated: Generated = generate_checked(llm, PORTFOLIO_SYSTEM_PROMPT, user, allowed_from(*lines),
                                            lambda: _template(proposal), max_sentences=7)
    return PortfolioExplanationResponse(
        explanation=generated.text, model=generated.model, fallback_used=generated.fallback_used,
        fallback_reason=generated.fallback_reason, stale=False, **common)
