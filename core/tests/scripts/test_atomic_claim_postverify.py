"""#1989 — atomic_claim.sh TOCTOU hardening contract tests.

বাংলা: claim-then-verify-এর পর label-add-এর পরেও একটি re-read থাকতে হবে
(post-verify) — assignee eviction ধরা পড়বে, label নিশ্চিত হবে; আর
`status:planned` থেকে `status:in-progress`-এ গেলে stale planned label সরানো
হবে।
"""

from __future__ import annotations

from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "ci" / "atomic_claim.sh"


class TestPostVerifyHardening:
    def test_script_exists_and_valid_bash(self):
        assert SCRIPT.exists()
        import subprocess

        result = subprocess.run(["bash", "-n", str(SCRIPT)], capture_output=True)
        assert result.returncode == 0, result.stderr.decode()

    def test_post_verify_step_present(self):
        text = SCRIPT.read_text(encoding="utf-8")
        assert "STEP 3.5" in text or "POST-VERIFY" in text, "post-verify step missing"
        assert "Post-verify FAILED" in text, "eviction branch must exist"
        assert "ME_STILL_ASSIGNED" in text
        assert "FINAL_HAS_LABEL" in text

    def test_eviction_releases_label(self):
        """Raced-and-evicted claimants must release the status label (no zombie holds)."""
        text = SCRIPT.read_text(encoding="utf-8")
        remove_block = text[text.find("ME_STILL_ASSIGNED") : text.find("STEP 4")]
        assert "--remove-label" in remove_block, "evicted claim must remove its status label"
        assert "exit 1" in remove_block

    def test_cas_core_unchanged(self):
        """The existing CAS machinery (claim → verify → evict-others) stays intact."""
        text = SCRIPT.read_text(encoding="utf-8")
        for marker in (
            "STEP 1: CLAIM",
            "STEP 2: VERIFY",
            "Removing other assignees",
            "STEP 3: LOCK",
        ):
            assert marker in text, f"existing CAS stage missing: {marker}"
