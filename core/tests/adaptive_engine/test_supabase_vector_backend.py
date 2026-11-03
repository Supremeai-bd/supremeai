"""
SupabaseVectorBackend.query — dimension-mismatch observability tests (#2257).

Contract under test: experience recall through the match_experiences RPC must
degrade OBSERVABLY (WARNING + fix pointer) when the RPC rejects calls — the
historical behavior was a silent debug-level return of [] (the VECTOR(1536)
RPC variant rejected every canonical 384-dim call, killing experience recall
with zero signal). Happy path must keep working against the re-typed (384)
RPC. All Supabase I/O is mocked — no live DB.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from adaptive_engine.supabase_vector_backend import SupabaseVectorBackend  # noqa: E402


def _backend_with_client():
    """Backend with a mocked Supabase client (_available pre-cached True)."""
    backend = SupabaseVectorBackend.__new__(SupabaseVectorBackend)
    client = MagicMock()
    backend.supabase_db = MagicMock()
    backend.supabase_db.client = client
    backend._available = True  # cached availability — mirrors __init__ state
    backend.COLLECTION_NAME = "experience"
    return backend, client


def _rpc_result(rows):
    resp = MagicMock()
    resp.data = rows
    rpc = MagicMock()
    rpc.execute.return_value = resp
    client_rpc = MagicMock(return_value=rpc)
    return client_rpc, rpc


def test_query_happy_path_maps_rows():
    backend, client = _backend_with_client()
    rows = [
        {"id": "u1", "summary": "alpha", "metadata": {"k": 1}, "similarity": 0.91},
        {"id": "u2", "summary": "beta", "metadata": "{}", "similarity": 0.42},
    ]
    client_rpc, _ = _rpc_result(rows)
    client.rpc = client_rpc

    out = backend.query(query_embedding=[0.1] * 384, limit=5)

    assert [r["id"] for r in out] == ["u1", "u2"]
    assert out[0]["similarity"] == pytest.approx(0.91)
    assert out[1]["metadata"] == {}  # JSON-string metadata parsed
    # RPC invoked with the canonical 384-dim embedding (params = 2nd positional)
    args, _kwargs = client_rpc.call_args
    assert args[0] == "match_experiences"
    assert len(args[1]["query_embedding"]) == 384


def test_query_dimension_error_is_observable_not_silent():
    """VECTOR(1536)-typed RPC rejects a 384-dim call → WARNING with the
    migration pointer, [] returned, NO exception raised."""
    from adaptive_engine import supabase_vector_backend as svb_mod

    backend, client = _backend_with_client()
    failing = MagicMock(
        return_value=MagicMock(
            execute=MagicMock(
                side_effect=Exception("expected query embedding to have length 1536, not 384")
            )
        )
    )
    client.rpc = failing

    with patch.object(svb_mod.logger, "warning") as warn:
        out = backend.query(query_embedding=[0.1] * 384)

    assert out == []
    assert warn.called, "degradation must surface at WARNING, not debug"
    msg = " ".join(str(c.args[0]) for c in warn.call_args_list if c.args)
    assert "17_retype_match_experiences_384.sql" in msg
    assert "dimension" in msg.lower()


def test_query_unavailable_backend_returns_empty():
    backend = SupabaseVectorBackend.__new__(SupabaseVectorBackend)
    backend._available = False
    assert backend.query(query_embedding=[0.1] * 384) == []
