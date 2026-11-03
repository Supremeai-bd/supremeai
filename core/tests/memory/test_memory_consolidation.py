"""M01 P-A (PLAN_006) — similarity-gated memory consolidation tests.

বাংলা: একই তথ্য = একটি সারি। pg-পথের store_memory আগে অন্ধভাবে INSERT
করত — এখন (user_id, session_id)-স্কোপে কসাইন-প্রোব হয়; সদৃশ হলে UPDATE
(metadata-importance bump সহ), না হলে/কিল-সুইচ অফ হলে/probe ব্যর্থ হলে
আজকের blind INSERT। প্রতিটি শাখা এখানে পিন করা।
"""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from services import memory_service as memory_service_module
from services.memory_service import CascadeMemoryService, memory_dedup_enabled

pytestmark = pytest.mark.memory


def _make_pg_service() -> CascadeMemoryService:
    with patch("services.memory_service.pooled_pg") as mock_pg:
        mock_pg.is_available.return_value = True
        service = CascadeMemoryService()
    assert service._use_pg
    return service


def _row(
    row_id: str, vector: list[float], metadata: dict[str, Any] | None = None
) -> dict[str, Any]:
    return {
        "id": row_id,
        "summary": "existing summary",
        "embedding": json.dumps(vector),
        "metadata": json.dumps(metadata or {}),
    }


class FakePg:
    """Records execute()/query_dicts() SQL; serves canned rows from query_dicts().

    বাংলা মন্তব্য (#2597 triage): Single Writer Law (#2427 seq:2) অনুযায়ী
    blind-INSERT এখন ``query_dicts(... RETURNING id)`` পথে যায় — আগের
    ``execute()``-only রেকর্ডিংয়ে INSERT-শাখার চুক্তি-টেস্ট সাইলেন্টলি খালি
    ``executed`` দেখে ফেইল করত (প্রমাণ: PR #2598 Test & Build)। দুই পথই
    রেকর্ড করা হলো — caller যে-পথই নিক।"""

    def __init__(self, rows: list[dict[str, Any]] | Exception):
        self.rows = rows
        self.executed: list[tuple[str, tuple]] = []

    def query_dicts(self, sql, params=None):
        self.executed.append((sql.strip(), params or ()))
        if isinstance(self.rows, Exception):
            raise self.rows
        return self.rows

    def execute(self, sql, params=None):
        self.executed.append((sql.strip(), params or ()))

    @property
    def writes(self) -> list[tuple[str, tuple]]:
        """Only the mutating statements (UPDATE/INSERT/DELETE) — probe SELECTs excluded.

        বাংলা: probe-SELECT (consolidation) ও লেখা একই query_dicts পথে আসে;
        চুক্তি-টেস্ট শুধু লেখাই দেখবে — এই সংস্করণটি #2597 triage-এ যোগ হলো।"""
        return [
            e for e in self.executed if not e[0].lstrip().upper().startswith(("SELECT", "WITH"))
        ]


UNIT = [1.0, 0.0, 0.0, 0.0]
ORTHOGONAL = [0.0, 1.0, 0.0, 0.0]


def _patch_embed(svc: CascadeMemoryService, vector: list[float]) -> None:
    svc._embed = lambda text: vector  # type: ignore[method-assign]


# ---------------------------------------------------------------------------
# Kill-switch + threshold helpers
# ---------------------------------------------------------------------------


def test_dedup_defaults_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP", raising=False)
    assert memory_dedup_enabled() is True


def test_dedup_kill_switch_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_MEMORY_DEDUP", "false")
    assert memory_dedup_enabled() is False


def test_dedup_unknown_value_warns_and_defaults(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # loguru-logger caplog-অদৃশ্য — module-logger-ই প্যাচ করা হয়।
    fake_logger = MagicMock()
    monkeypatch.setattr(memory_service_module, "logger", fake_logger)
    monkeypatch.setenv("SUPREMEAI_MEMORY_DEDUP", "maybe")
    assert memory_dedup_enabled() is True
    assert fake_logger.warning.called
    assert "SUPREMEAI_MEMORY_DEDUP" in str(fake_logger.warning.call_args)


def test_threshold_env_override_and_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_MEMORY_DEDUP_THRESHOLD", "0.8")
    assert memory_service_module._dedup_similarity_threshold() == 0.8

    fake_logger = MagicMock()
    monkeypatch.setattr(memory_service_module, "logger", fake_logger)
    monkeypatch.setenv("SUPREMEAI_MEMORY_DEDUP_THRESHOLD", "garbage")
    assert memory_service_module._dedup_similarity_threshold() == 0.92
    assert fake_logger.warning.called
    assert "garbage" in str(fake_logger.warning.call_args)


# ---------------------------------------------------------------------------
# store_memory pg-path branches
# ---------------------------------------------------------------------------


def test_similar_summary_consolidates_into_existing_row(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP", raising=False)
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP_THRESHOLD", raising=False)
    svc = _make_pg_service()
    _patch_embed(svc, UNIT)
    fake = FakePg([_row("mem-1", UNIT)])
    with patch.object(memory_service_module, "pooled_pg", fake):
        svc.store_memory(
            file_path="f.py",
            content="c",
            summary="same meaning",
            structure="{}",
            session_id="s1",
            agent_type="agent",
            task_type="general",
            user_id="u1",
        )
    assert len(fake.writes) == 1
    sql, params = fake.writes[0]
    assert sql.startswith("UPDATE ai_memory")
    merged_meta = json.loads(params[2])
    assert merged_meta["consolidation"]["count"] == 2  # আগের সারির ১ → এখন ২
    assert merged_meta["importance_score"] == pytest.approx(0.6)  # 0.5 + 0.1 bump


def test_dissimilar_summary_blind_inserts(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP", raising=False)
    svc = _make_pg_service()
    _patch_embed(svc, ORTHOGONAL)
    fake = FakePg([_row("mem-1", UNIT)])
    with patch.object(memory_service_module, "pooled_pg", fake):
        svc.store_memory(
            file_path="f.py",
            content="c",
            summary="different topic entirely",
            structure="{}",
            session_id="s1",
            user_id="u1",
        )
    assert len(fake.writes) == 1
    assert fake.writes[0][0].startswith("INSERT INTO ai_memory")


def test_kill_switch_disables_consolidation(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SUPREMEAI_MEMORY_DEDUP", "false")
    svc = _make_pg_service()
    _patch_embed(svc, UNIT)  # পরিচিত সদৃশ ভেক্টর সত্ত্বেও
    fake = FakePg([_row("mem-1", UNIT)])
    with patch.object(memory_service_module, "pooled_pg", fake):
        svc.store_memory(
            file_path="f.py",
            content="c",
            summary="same",
            structure="{}",
            session_id="s1",
            user_id="u1",
        )
    assert fake.writes[0][0].startswith("INSERT INTO ai_memory")


def test_unscoped_write_skips_dedup_tenant_isolation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP", raising=False)
    svc = _make_pg_service()
    _patch_embed(svc, UNIT)
    fake = FakePg([_row("mem-1", UNIT)])
    with patch.object(memory_service_module, "pooled_pg", fake):
        # user_id/session_id শূন্য — tenant-বহির্ভূত probe নিষিদ্ধ
        svc.store_memory(file_path="f.py", content="c", summary="same", structure="{}")
    assert fake.writes[0][0].startswith("INSERT INTO ai_memory")


def test_probe_failure_falls_back_to_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP", raising=False)
    svc = _make_pg_service()
    _patch_embed(svc, UNIT)
    fake = FakePg(RuntimeError("pg down"))
    with patch.object(memory_service_module, "pooled_pg", fake):
        svc.store_memory(
            file_path="f.py",
            content="c",
            summary="same",
            structure="{}",
            session_id="s1",
            user_id="u1",
        )
    assert fake.writes[0][0].startswith("INSERT INTO ai_memory")


def test_threshold_env_uses_custom_boundary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP", raising=False)
    monkeypatch.setenv("SUPREMEAI_MEMORY_DEDUP_THRESHOLD", "0.5")
    svc = _make_pg_service()
    # 0.5-সীমায় 45°-ভেক্টরও সদৃশ (cosine ≈ 0.707)
    diag = [0.7071067811865476, 0.7071067811865476, 0.0, 0.0]
    _patch_embed(svc, diag)
    fake = FakePg([_row("mem-1", UNIT)])
    with patch.object(memory_service_module, "pooled_pg", fake):
        svc.store_memory(
            file_path="f.py",
            content="c",
            summary="related",
            structure="{}",
            session_id="s1",
            user_id="u1",
        )
    assert fake.writes[0][0].startswith("UPDATE ai_memory")


def test_corrupted_embedding_rows_are_skipped_not_fatal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP", raising=False)
    svc = _make_pg_service()
    _patch_embed(svc, UNIT)
    broken = _row("mem-broken", UNIT)
    broken["embedding"] = "not-json{"
    fake = FakePg([broken, _row("mem-good", UNIT)])
    with patch.object(memory_service_module, "pooled_pg", fake):
        svc.store_memory(
            file_path="f.py",
            content="c",
            summary="same",
            structure="{}",
            session_id="s1",
            user_id="u1",
        )
    assert fake.writes[0][0].startswith("UPDATE ai_memory")  # সুস্থ সারিতে মার্জ


def test_importance_bump_is_capped_at_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SUPREMEAI_MEMORY_DEDUP", raising=False)
    svc = _make_pg_service()
    _patch_embed(svc, UNIT)
    fake = FakePg([_row("mem-1", UNIT, {"importance_score": 0.98})])
    with patch.object(memory_service_module, "pooled_pg", fake):
        svc.store_memory(
            file_path="f.py",
            content="c",
            summary="same",
            structure="{}",
            session_id="s1",
            user_id="u1",
        )
    merged_meta = json.loads(fake.writes[0][1][2])
    assert merged_meta["importance_score"] == 1.0
