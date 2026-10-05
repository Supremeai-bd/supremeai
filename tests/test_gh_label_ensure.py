"""Tests for gh_label_ensure.py (#3278) — issue-filing funnel revival."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from scripts.agents.gh_label_ensure import (
    LabelEnsureError,
    _existing_labels,
    ensure_labels,
    main,
)


class _FakeGh:
    """subprocess.run নকল — gh label list/create আচরণ সিমুলেট।"""

    def __init__(self, existing: set[str], create_fails: dict[str, str] | None = None):
        self.existing = set(existing)
        self.create_fails = create_fails or {}
        self.create_calls: list[str] = []

    def __call__(self, cmd, **kwargs):
        if "label" in cmd and "list" in cmd:
            payload = json.dumps([{"name": n} for n in sorted(self.existing)])
            return subprocess.CompletedProcess(cmd, 0, stdout=payload, stderr="")
        if "label" in cmd and "create" in cmd:
            label = cmd[cmd.index("create") + 1]
            self.create_calls.append(label)
            if label in self.create_fails:
                return subprocess.CompletedProcess(
                    cmd, 1, stdout="", stderr=self.create_fails[label]
                )
            self.existing.add(label)
            return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="unexpected cmd")


@pytest.fixture(autouse=True)
def _clear_cache():
    _existing_labels.cache_clear()
    yield
    _existing_labels.cache_clear()


class TestEnsureLabels:
    def test_all_existing_no_create(self, monkeypatch):
        fake = _FakeGh(existing={"type:security", "P1-high"})
        monkeypatch.setattr(subprocess, "run", fake)
        result = ensure_labels(["type:security", "P1-high"])
        assert result == ["type:security", "P1-high"]
        assert fake.create_calls == []

    def test_missing_label_created(self, monkeypatch):
        fake = _FakeGh(existing={"status:unclaimed"})
        monkeypatch.setattr(subprocess, "run", fake)
        result = ensure_labels(["type:vulnerability", "status:unclaimed"])
        assert result == ["type:vulnerability", "status:unclaimed"]
        assert fake.create_calls == ["type:vulnerability"]
        # idempotent: দ্বিতীয় কলে আর create হবে না (এখন existing-এ আছে)
        _existing_labels.cache_clear()
        result2 = ensure_labels(["type:vulnerability", "status:unclaimed"])
        assert result2 == ["type:vulnerability", "status:unclaimed"]
        assert fake.create_calls == ["type:vulnerability"]

    def test_race_already_exists_tolerated(self, monkeypatch):
        # সমান্তরাল creator-এ লেবেল ইতিমধ্যে তৈরি → "already exists" = সাফল্য
        fake = _FakeGh(existing=set())
        fake.create_fails = {"new-label": "could not create: label already exists"}
        monkeypatch.setattr(subprocess, "run", fake)
        result = ensure_labels(["new-label"])
        assert result == ["new-label"]

    def test_create_failure_raises(self, monkeypatch):
        fake = _FakeGh(existing=set())
        fake.create_fails = {"broken": "gh: Not Found (HTTP 404)"}
        monkeypatch.setattr(subprocess, "run", fake)
        with pytest.raises(LabelEnsureError, match="broken"):
            ensure_labels(["broken"])

    def test_list_failure_raises(self, monkeypatch):
        def failing(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="auth error")

        monkeypatch.setattr(subprocess, "run", failing)
        with pytest.raises(LabelEnsureError, match="label list"):
            ensure_labels(["anything"])

    def test_dedup_and_blank_strip(self, monkeypatch):
        fake = _FakeGh(existing={"a", "b"})
        monkeypatch.setattr(subprocess, "run", fake)
        result = ensure_labels(["a", " a ", "", "  ", "b", "a"])
        assert result == ["a", "b"]

    def test_empty_input(self, monkeypatch):
        fake = _FakeGh(existing={"x"})
        monkeypatch.setattr(subprocess, "run", fake)
        assert ensure_labels([]) == []
        assert ensure_labels(["", "  "]) == []

    def test_cache_single_list_call(self, monkeypatch):
        # একাধিক ensure_labels কলেও প্রতি cache-জীবনে একটিই list-কল
        fake = _FakeGh(existing={"x"})
        monkeypatch.setattr(subprocess, "run", fake)
        ensure_labels(["x"])
        ensure_labels(["x"])
        list_calls = [c for c in fake.create_calls]  # create হয়নি
        assert list_calls == []


class TestCli:
    def test_cli_success_quiet(self, monkeypatch, capsys):
        fake = _FakeGh(existing={"P1-high"})
        monkeypatch.setattr(subprocess, "run", fake)
        rc = main(["P1-high", "--quiet"])
        assert rc == 0
        assert capsys.readouterr().out.strip() == "P1-high"

    def test_cli_creates_missing(self, monkeypatch, capsys):
        fake = _FakeGh(existing=set())
        monkeypatch.setattr(subprocess, "run", fake)
        rc = main(["type:vulnerability"])
        assert rc == 0
        assert "type:vulnerability" in capsys.readouterr().out

    def test_cli_infra_failure_nonzero(self, monkeypatch, capsys):
        def failing(cmd, **kwargs):
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="boom")

        monkeypatch.setattr(subprocess, "run", failing)
        rc = main(["x"])
        assert rc == 1


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
