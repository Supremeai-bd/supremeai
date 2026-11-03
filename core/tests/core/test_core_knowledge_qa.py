import os
import sys

backend_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# বাংলা মন্তব্য: অন্য টেস্ট কেসগুলোকে প্রভাবিত করা এড়াতে sys.path এবং sys.modules সাময়িকভাবে ব্যাকআপ নিয়ে পরিবর্তন করা হলো এবং পরে পুনরুদ্ধার করা হলো।
orig_path = sys.path.copy()
orig_skills = sys.modules.get("skills")

try:
    if backend_path not in sys.path:
        sys.path.insert(0, backend_path)

    root_skills = os.path.normpath(os.path.join(backend_path, "..", "skills")).lower()
    root_dir = os.path.normpath(os.path.join(backend_path, "..")).lower()
    sys.path = [
        p
        for p in sys.path
        if os.path.normpath(p).lower() != root_skills and os.path.normpath(p).lower() != root_dir
    ]
    sys.modules.pop("skills", None)

    from core.skills import core_knowledge_qa
finally:
    sys.path = orig_path
    if orig_skills is not None:
        sys.modules["skills"] = orig_skills
    else:
        sys.modules.pop("skills", None)


from unittest.mock import MagicMock, patch


def test_vector_search_returns_empty_when_supabase_not_configured():
    """Supabase কনফিগার করা না থাকলে fabricated ডেটা না দিয়ে খালি লিস্ট রিটার্ন করা উচিত।"""
    fake_db = MagicMock()
    fake_db.client = None
    with patch("database.supabase_client.db", fake_db):
        result = core_knowledge_qa._vector_search("what is the office timing", "public_sops")
    assert result == []


def test_vector_search_uses_real_rpc_not_hardcoded_dict():
    """query যাই হোক, ফলাফল আসা উচিত real client.rpc() কল থেকে — hardcoded dict থেকে নয়।"""
    fake_client = MagicMock()
    fake_client.rpc.return_value.execute.return_value = MagicMock(
        data=[
            {
                "id": "doc_99",
                "content": "Real retrieved content",
                "source": "Real Source",
            }
        ]
    )
    fake_db = MagicMock()
    fake_db.client = fake_client

    with (
        patch("database.supabase_client.db", fake_db),
        patch.object(core_knowledge_qa, "_generate_embedding", return_value=[0.1] * 1536),
    ):
        result = core_knowledge_qa._vector_search("any arbitrary query text", "public_sops")

    fake_client.rpc.assert_called_once()
    assert result == [
        {"id": "doc_99", "content": "Real retrieved content", "source": "Real Source"}
    ]


def test_execute_tool_returns_no_documents_message_when_nothing_found():
    fake_db = MagicMock()
    fake_db.client = None
    with patch("database.supabase_client.db", fake_db):
        result = core_knowledge_qa.execute_tool({"user_role": "Standard_User", "query": "anything"})
    assert result["success"] is True
    assert result["result"]["citations"] == []
