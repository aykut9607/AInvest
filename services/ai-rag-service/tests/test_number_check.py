from decimal import Decimal

from core.number_check import allowed_from, allowed_values, verify_numbers
from services.explainer import template_explanation


def test_score_and_100_are_the_only_numbers_the_coach_may_write():
    allowed = allowed_values(55, 100)
    assert verify_numbers("Skorun 100 üzerinden 55, yani 55/100.", allowed).verified
    assert verify_numbers("Skorun 55, ama 3 ay içinde artabilir.", allowed).unknown == ("3",)


def test_factor_points_are_rejected_even_though_they_are_real_data():
    # the coach never sees factor points; writing them means it guessed (it once wrote 20/20 for a 15/15 factor)
    assert verify_numbers("Nakit rezervin 25 üzerinden 8 puan aldı.", allowed_values(55, 100)).unknown == ("25", "8")


def test_percentages_pass_only_when_the_data_has_that_percentage():
    allowed = allowed_from("Taksitin aylık gelire oranı: %13", "Aylık gelir: 30.000 TL")
    assert verify_numbers("Gelirinin %13'ü taksite gidiyor.", allowed).verified
    assert verify_numbers("Gelirinin 13% kadarı taksite gidiyor.", allowed).verified
    # 30.000 is in the data, but never as a percentage
    assert verify_numbers("Gelirinin %30'u.", allowed).unknown == ("%30",)


def test_numbers_copied_from_the_data_block_pass_in_turkish_formats():
    allowed = allowed_from("Aylık kalan para: 12.500 TL", "Acil durum fonu 4,5 aylık gideri karşılıyor")
    assert verify_numbers("Her ay 12.500 TL kalıyor, fonun 4,5 ay yetiyor.", allowed).verified
    assert verify_numbers("Her ay 12500 TL kalıyor.", allowed).verified           # same value without the dot
    assert verify_numbers("Her ay 12.000 TL kalıyor.", allowed).unknown == ("12.000",)


def test_dates_in_words_are_allowed_number_by_number():
    allowed = allowed_from("İlk hesaplama: 1 Kasım 2026, skor 8")
    assert verify_numbers("1 Kasım 2026'da skorun 8 idi.", allowed).verified


def test_list_markers_are_not_treated_as_claims():
    assert verify_numbers("1. Skorun 55.\n2) Nakit rezervin zayıf.", allowed_values(55, 100)).verified


def test_template_only_shows_numbers_from_the_request(medium_request):
    # the template may show factor points (it is deterministic), but never anything that is not in the request
    data = {medium_request.score, 100, *medium_request.factor_breakdown.factors.values(), 25, 15, 10}
    assert verify_numbers(template_explanation(medium_request), allowed_values(*data)).verified
    assert Decimal(55) in allowed_values(55).values
