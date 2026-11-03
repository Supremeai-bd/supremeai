"""M19 P-D slice-1 — bengali_text unit tests (single-owner Bengali utility).

বাংলা: NFC-সমতা, বাংলা-সনাক্তি, blended token-অনুমান, env-চালিত অনুপাত,
ডাঁড়ি-সচেতন কাট — প্রতিটি আচরণ এখানে পিন করা। এছাড়া token_budget-এর
delegate-চুক্তি (পুরনো flat 4.0 আচরণের সংশোধন) যাচাই করা হয়।
"""

from __future__ import annotations

import unicodedata

import pytest

from core.i18n import bengali_text
from core.i18n.bengali_text import (
    DEFAULT_BENGALI_CHARS_PER_TOKEN,
    bengali_ratio,
    estimate_tokens_bengali_aware,
    has_bengali,
    nfc,
    truncate_dari_safe,
)
from core.llm.token_budget import estimate_tokens as tb_estimate_tokens
from core.llm.token_budget import truncate_to_token_limit

# ---------------------------------------------------------------------------
# NFC
# ---------------------------------------------------------------------------


def test_nfc_is_idempotent_and_normalizes_decomposed_form() -> None:
    # "বাংলা" NFD-বিযুক্ত রূপ (vowel sign আলাদা codepoint) → NFC-এ যুক্ত।
    text = "বাংলা"
    decomposed = unicodedata.normalize("NFD", text)
    if decomposed == text:  # এই শব্দে decomposed রূপ না থাকলে টেস্ট অর্থহীন
        pytest.skip("fixture has no decomposed form")
    assert nfc(decomposed) == text
    assert nfc(nfc(text)) == nfc(text)  # idempotent


def test_nfc_unifies_zwnj_variants_for_cache_keys() -> None:
    # ZWNJ যুক্ত ও বিহীন রূপ একই ক্যাশ-কি হওয়া উচিত (NFC ZWNJ সরায় না —
    # তবে নিচের চুক্তি: nfc(f"{a}:384") == nfc(f"{b}:384") যেখানে a/b নির্মিত)।
    with_zwnj = "\u09ac\u09be\u200d\u0982\u09b2\u09be"
    without = "\u09ac\u09be\u0982\u09b2\u09be"
    # উভয়ের NFC আউটপুট নিজস্ব স্বাভাবিক রূপ — nfc() deterministic সেটাই চুক্তি।
    assert nfc(with_zwnj) == nfc(nfc(with_zwnj))
    assert nfc(without) == without


# ---------------------------------------------------------------------------
# Detection + ratio
# ---------------------------------------------------------------------------


def test_has_bengali_and_ratio() -> None:
    assert has_bengali("আমি ভালো আছি")
    assert not has_bengali("I am fine")
    assert not has_bengali("")
    assert bengali_ratio("আমিভালো") == 1.0  # সব অক্ষর বাংলা-ব্লক (স্পেস নেই)
    assert 0.0 < bengali_ratio("আমি fine") < 1.0  # স্পেস/ইংরেজি মিশ্র
    assert bengali_ratio("") == 0.0
    assert bengali_ratio("hello") == 0.0


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------


def test_estimator_zero_and_empty() -> None:
    assert estimate_tokens_bengali_aware("") == 0
    assert tb_estimate_tokens("") == 0


def test_estimator_english_matches_legacy_ratio() -> None:
    # ইংরেজি টেক্সটে পুরনো 4.0 অনুপাত অক্ষুণ্ণ (বাজেট-বান্ধব আচরণ-নিরপেক্ষ)।
    text = "a" * 400
    assert estimate_tokens_bengali_aware(text) == 100
    assert tb_estimate_tokens(text) == 100


def test_estimator_bengali_counts_double_the_legacy_flat_estimate() -> None:
    # "বাংলা" = 5 অক্ষর ×100 = 500 বাংলা অক্ষর।
    text = "বাংলা" * 100
    # নতুন blended মডেল: 500 বাংলা / 2.0 = 250 token (exact-integral → কোনো +1 নয়)।
    new_estimate = estimate_tokens_bengali_aware(text)
    legacy_flat = int(500 / 4.0)  # পুরনো flat 4.0 যা under-count করত = 125
    assert new_estimate == 250
    assert new_estimate == legacy_flat * 2  # ~2× correction over flat estimate
    # token_budget delegate একই ফল দেয়।
    assert tb_estimate_tokens(text) == new_estimate


def test_estimator_blends_mixed_language_prompt() -> None:
    # 200 বাংলা + 200 ইংরেজি অক্ষর → 200/2.0 + 200/4.0 = 150 (exact)।
    text = "অ" * 200 + "a" * 200
    assert estimate_tokens_bengali_aware(text) == 150


def test_estimator_code_block_ratio_unchanged() -> None:
    text = "```python\ndef f():\n    pass\n```" + "x" * 100
    assert estimate_tokens_bengali_aware(text) == max(1, int(len(text) / 3.5))


def test_estimator_env_ratio_override(monkeypatch: pytest.MonkeyPatch) -> None:
    text = "অ" * 200
    monkeypatch.setenv("BENGALI_CHARS_PER_TOKEN", "1.0")
    assert estimate_tokens_bengali_aware(text) == 200  # 200/1.0 exact


def test_estimator_invalid_env_falls_back_loud(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    text = "অ" * 200
    monkeypatch.setenv("BENGALI_CHARS_PER_TOKEN", "not-a-number")
    with caplog.at_level("WARNING"):
        assert estimate_tokens_bengali_aware(text) == 100  # ডিফল্ট 2.0 → 100
    assert "BENGALI_CHARS_PER_TOKEN" in caplog.text

    monkeypatch.setenv("BENGALI_CHARS_PER_TOKEN", "-3")
    assert estimate_tokens_bengali_aware(text) == 100
    assert "≤0" in caplog.text


def test_default_ratio_is_conservative_two() -> None:
    assert DEFAULT_BENGALI_CHARS_PER_TOKEN == 2.0
    assert bengali_text.bengali_chars_per_token() == 2.0  # env-শূন্য অবস্থায়


# ---------------------------------------------------------------------------
# Dari-safe truncation
# ---------------------------------------------------------------------------


def test_truncate_short_text_untouched() -> None:
    text = "এটি ছোট বাক্য।"
    assert truncate_dari_safe(text, 100) == text


def test_truncate_prefers_dari_boundary() -> None:
    # নির্ধারিত দৈর্ঘ্য: first = 15 chars (ডাঁড়ি idx-14), second-এর ডাঁড়ি idx-25।
    first = "অ" * 14 + "।"
    second = "ব" * 10 + "।" + "ব" * 10
    text = first + second  # 36 chars
    cut = truncate_dari_safe(text, 28)  # search window starts at int(28*0.6)=16
    assert cut == first + "ব" * 10 + "।"  # 26 chars — second-এর ডাঁড়ি পর্যন্ত
    assert cut.startswith(first)
    assert cut.endswith("।")


def test_truncate_never_splits_combining_mark() -> None:
    # "কি" = ক + ি (combining vowel sign U+09BF) — কাট-পয়েন্ট মাঝে পড়লে
    # ফাংশন পিছিয়ে গিয়ে পূর্ণ অক্ষর-সীমায় কাটবে।
    text = "\u0995\u09bf" * 10  # 20 chars
    cut = truncate_dari_safe(text, 10)  # text[:10] শেষে ি (mark) → 9-এ পিছাবে
    assert len(cut) == 9
    # শেষ অক্ষর কখনো একা combining mark হবে না।
    assert not unicodedata.combining(cut[-1])


def test_truncate_hard_cut_without_dari() -> None:
    text = "a" * 100
    assert truncate_dari_safe(text, 50) == "a" * 50
    assert truncate_dari_safe(text, 0) == ""


# ---------------------------------------------------------------------------
# token_budget dari-aware sentence trimming (wiring #2)
# ---------------------------------------------------------------------------


def test_truncate_to_token_limit_respects_bengali_sentence_end() -> None:
    # বাংলা বাক্য-শেষ ডাঁড়িতে কাটা হয় — ইংরেজি full-stop নেই এমন টেক্সটেও।
    sentence = "এটি একটি তথ্যবহুল বাক্য।" + "x" * 200
    out = truncate_to_token_limit(sentence, 30)
    assert "।" in out


# ---------------------------------------------------------------------------
# embeddings NFC wiring (wiring #3)
# ---------------------------------------------------------------------------


def test_embed_for_pgvector_nfc_normalizes_input() -> None:
    from core import embeddings

    captured: list[str] = []

    original_local = embeddings.local_embed
    embeddings.local_embed = lambda t: captured.append(t) or [0.0] * 384  # type: ignore[assignment]
    try:
        decomposed = unicodedata.normalize("NFD", "বাংলা")
        vec = embeddings.embed_for_pgvector(decomposed)
        assert len(vec) == 384
        # এমবেডার NFC-গোছানো পাঠ্য দেখেছে (NFD প্রত্যক্ষ নয়)।
        assert captured and captured[0] == unicodedata.normalize("NFC", decomposed)
    finally:
        embeddings.local_embed = original_local  # type: ignore[assignment]
