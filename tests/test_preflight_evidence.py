import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "scripts" / "ci"))
from verify_preflight_evidence import verify


def valid_payload():
    return {
        "schema_version": "1.0",
        "generated_at": "2026-09-07T00:00:00+00:00",
        "status": "ready",
        "required_roles": [],
        "accounts": [],
        "route_inventory": {"status": "valid", "sha256": "a" * 64, "route_count": 447},
    }


def test_valid_evidence(tmp_path):
    path = tmp_path / "evidence.json"
    path.write_text(json.dumps(valid_payload()), encoding="utf-8")
    assert verify(path) == []


def test_missing_schema_is_rejected(tmp_path):
    path = tmp_path / "evidence.json"
    payload = valid_payload()
    del payload["schema_version"]
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert "missing key: schema_version" in verify(path)


class TestPreflightEvidence(unittest.TestCase):
    def test_valid_evidence(self):
        path = self._write(valid_payload())
        self.assertEqual(verify(path), [])

    def test_missing_schema_is_rejected(self):
        payload = valid_payload()
        del payload["schema_version"]
        self.assertIn("missing key: schema_version", verify(self._write(payload)))

    def test_invalid_inventory_digest_is_rejected(self):
        payload = valid_payload()
        payload["route_inventory"]["sha256"] = "bad"
        self.assertIn("valid route inventory must include a SHA-256 digest", verify(self._write(payload)))

    def _write(self, payload):
        import tempfile
        handle = tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False, encoding="utf-8")
        with handle:
            json.dump(payload, handle)
        return Path(handle.name)
