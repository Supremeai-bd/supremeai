from memory.long_term_memory import LongTermMemory


def test_long_term_memory_remember_and_recall():
    mem = LongTermMemory(db_path=":memory:", session_id="s1")
    mem.remember_fact(
        content="User likes Bengali food",
        category="preference",
        importance=0.9,
        source="chat",
    )
    facts = mem.recall_facts(category="preference")
    assert len(facts) == 1
    assert facts[0]["content"] == "User likes Bengali food"
    assert facts[0]["importance"] == 0.9


def test_long_term_memory_build_context():
    mem = LongTermMemory(db_path=":memory:", session_id="s2")
    mem.remember_fact("Bangla is native", category="language")
    mem.save_summary("Discussed Bengali AI features", turn_count=3)
    context = mem.build_context()
    assert "Bengali AI features" in context
    assert "Bangla is native" in context
