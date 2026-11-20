from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Self

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from scripts.ci import check_opportunistic_audit as audit


class _Response:
    def __init__(self, payload: dict[str, object]) -> None:
        self._payload = payload

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return json.dumps(self._payload).encode("utf-8")


def test_runner_probe_tries_later_token_after_successful_empty_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tokens = ["first-token", "second-token"]
    calls: list[str | None] = []

    monkeypatch.setattr(audit, "_get_candidate_tokens", lambda: tokens)

    def fake_urlopen(request: Any, timeout: float) -> _Response:
        del timeout
        calls.append(request.get_header("Authorization"))
        if len(calls) == 1:
            return _Response({"runners": []})
        return _Response(
            {
                "runners": [
                    {
                        "name": "local-pc-1",
                        "status": "online",
                        "labels": [{"name": "local-pc"}],
                    }
                ]
            }
        )

    monkeypatch.setattr(audit.urllib.request, "urlopen", fake_urlopen)

    assert audit.is_local_runner_online(timeout=1.0) is True
    assert calls == ["Bearer first-token", "Bearer second-token"]


@pytest.mark.parametrize(
    ("content", "expected"),
    [("{", 0.0), ("[]", 0.0), ('{"timestamp":null}', 0.0), ('{"timestamp":42}', 42.0)],
)
def test_marker_timestamp(monkeypatch, tmp_path, content, expected):
    marker = tmp_path / "audit.json"
    monkeypatch.setattr(audit, "AUDIT_MARKER_FILE", marker)
    assert audit.get_last_audit_timestamp() == 0.0
    marker.write_text(content, encoding="utf-8")
    assert audit.get_last_audit_timestamp() == expected
