import pytest

from core.language_check import foreign_letters


def test_turkish_letters_and_symbols_pass():
    text = "Çağrı, İşçi, öğün, şüphe; hâlâ, îmâ, Hûlya. Skorun 55 / 100 (%), “sen” — iyi! 🙂"
    assert foreign_letters(text) == []


@pytest.mark.parametrize("text, expected", [
    # taken from a real Qwen 2.5 14B answer (synth-0174)
    ("你的财务IQ得分为92分", ["你", "的", "财"]),
    # Turkish that drifts into Chinese mid-sentence (synth-0207)
    ("Senin finansal durumun güçlü, bu da senin偏好设置", ["偏", "好", "设"]),
    ("Финансовый IQ", ["Ф", "и", "н"]),
    ("スコアは55", ["ス", "コ", "ア"]),
])
def test_other_scripts_are_reported(text, expected):
    assert foreign_letters(text)[:3] == expected


def test_each_foreign_letter_is_reported_once():
    assert foreign_letters("的的的 a 的") == ["的"]
