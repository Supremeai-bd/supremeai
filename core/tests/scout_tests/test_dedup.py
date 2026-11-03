"""Unit tests for ContentDeduplicator."""

from scout.dedup import ContentDeduplicator


def test_exact_duplicate_detection():
    dedup = ContentDeduplicator()
    text = "Artificial Intelligence is transforming software development and robotics across the globe."

    h1, is_dup1 = dedup.record_content(text)
    assert not is_dup1
    assert len(h1) == 64

    # Exact same content
    h2, is_dup2 = dedup.record_content(text)
    assert is_dup2
    assert h1 == h2


def test_near_duplicate_detection():
    dedup = ContentDeduplicator(similarity_threshold=0.65)
    base_text = (
        "FastAPI is a modern, fast (high-performance), web framework for building APIs with Python 3.8+ "
        "based on standard Python type hints. The key features are fast to code and production ready."
    )
    # Slightly modified with a couple changed words
    near_dup = (
        "FastAPI is a modern, fast (high-performance), web framework for creating APIs with Python 3.8+ "
        "based on standard Python type hints. The primary features are fast to code and production ready."
    )
    # Completely different text
    different_text = (
        "PostgreSQL is a powerful, open source object-relational database system with over 35 years of active "
        "development that has earned it a strong reputation for reliability, feature robustness, and performance."
    )

    _, is_dup1 = dedup.record_content(base_text)
    assert not is_dup1

    # Near duplicate should be flagged
    assert dedup.is_duplicate(near_dup)
    _, is_dup2 = dedup.record_content(near_dup)
    assert is_dup2

    # Different text should be accepted
    assert not dedup.is_duplicate(different_text)
    _, is_dup3 = dedup.record_content(different_text)
    assert not is_dup3
