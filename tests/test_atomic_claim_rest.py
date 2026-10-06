"""Roadmap v2.0 Phase 0.5 regression guards (issue #4141).

The claim mutex (scripts/ci/atomic_claim.sh) is correctness-critical: its
universe scans MUST use REST lists (gh api --paginate --slurp), not the
eventually-consistent Search API behind `gh issue list` / `gh pr list --search`
(seq114/115 live evidence: fresh claims/PRs invisible → shared-identity
collisions + near-duplicate work).

Contract asserted here (text-level, same approach as the session-marker tests):
  * GAP-DUPLICATE-01 PR fallback scans REST /pulls (paginated).
  * Rule #13 active-claim scan scans REST /issues?labels=<status:in-progress>.
  * Group sibling boundary scan scans REST /issues with BOTH labels.
  * REST lists exclude PR objects via the `pull_request` discriminator.
  * No Search-API `gh issue list` / `gh pr list` remains on these paths.
"""

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
CLAIM_SH = REPO_ROOT / "scripts" / "ci" / "atomic_claim.sh"


class AtomicClaimRestUniverseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = CLAIM_SH.read_text(encoding="utf-8")

    def test_script_is_valid_bash(self):
        res = subprocess.run(
            ["bash", "-n", str(CLAIM_SH)], capture_output=True, text=True, check=False
        )
        self.assertEqual(res.returncode, 0, res.stderr)

    def test_pr_fallback_uses_rest_pulls(self):
        self.assertIn("repos/$GH_REPO/pulls?state=open&per_page=100", self.text)
        self.assertIn("--paginate --slurp", self.text)
        self.assertNotIn("gh pr list", self.text)

    def test_rule13_scan_uses_rest_issues_with_encoded_label(self):
        self.assertIn(
            'repos/$GH_REPO/issues?labels=$_ACTIVE_LABEL_ENC&state=open&per_page=100',
            self.text,
        )
        # label URL-encoding (status:in-progress → status%3Ain-progress)
        self.assertIn("sed 's/:/%3A/g'", self.text)

    def test_sibling_scan_uses_rest_with_both_labels(self):
        self.assertIn(
            "repos/$GH_REPO/issues?labels=$_GROUP_LABEL_ENC,$_ACTIVE_LABEL_ENC&state=open&per_page=100",
            self.text,
        )

    def test_rest_lists_exclude_pr_objects(self):
        """pull_request key = deterministic PR discriminator (#4123 pattern)."""
        self.assertEqual(
            self.text.count("i.get('pull_request') is None"), 2,
            "both /issues scans must exclude PR objects",
        )

    def test_no_search_api_left_on_claim_path(self):
        self.assertNotIn("gh issue list", self.text)

    def test_output_shape_unchanged_number_title(self):
        """Downstream consumers parse {number, title} JSON arrays."""
        self.assertEqual(
            self.text.count("{'number': i.get('number'), 'title': i.get('title', '')}"), 2
        )

    def test_fail_soft_semantics_preserved(self):
        """REST fetch failure degrades to the same '[]' as before (no fail-open
        to a hard crash; verify-claim remains the fail-closed backstop)."""
        self.assertGreaterEqual(self.text.count("|| echo \"[]\""), 2)


if __name__ == "__main__":
    unittest.main()
