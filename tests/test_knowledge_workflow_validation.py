"""Exercise the actual shared-knowledge workflow shell without external services."""
import os
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / '.github/workflows/unified-pipeline.yml'


def workflow_step():
    text = WORKFLOW.read_text(encoding='utf-8')
    step = text.split('      - name: Validate legacy shared knowledge (no storage)\n', 1)[1]
    return textwrap.dedent(step.split('        run: |\n', 1)[1])


def invoke(tmp_path, *, subject, share='', issue='', fail_on=''):
    bin_dir = tmp_path / 'bin'
    bin_dir.mkdir()
    git = bin_dir / 'git'
    git.write_text('#!/bin/sh\nprintf "%s\\n" "$TEST_SUBJECT"\n')
    git.chmod(0o755)
    python = bin_dir / 'python3'
    python.write_text('#!/bin/sh\nprintf "%s\\n" "$*" >> "$CALLS"\ncase "$*" in *"$FAIL_ON"*) [ -z "$FAIL_ON" ] || exit 7;; esac\n')
    python.chmod(0o755)
    summary = tmp_path / 'summary'
    calls = tmp_path / 'calls'
    env = dict(os.environ, PATH=f'{bin_dir}:' + os.environ['PATH'], TEST_SUBJECT=subject,
               DISPATCH_SHARE_JSON=share, DISPATCH_SCAN_ISSUE=issue, GH_REPO='owner/repo',
               GITHUB_STEP_SUMMARY=str(summary), CALLS=str(calls), FAIL_ON=fail_on)
    result = subprocess.run(['bash', '-e', '-o', 'pipefail', '-c', workflow_step()],
                            cwd=ROOT, env=env, capture_output=True, text=True)
    return result, calls.read_text().splitlines() if calls.exists() else [], summary.read_text()


def test_post_merge_and_dispatch_are_explicitly_validation_only(tmp_path):
    result, calls, summary = invoke(tmp_path, subject='change (#917)', share='{"insight":"sample"}', issue='45')
    assert result.returncode == 0
    assert len(calls) == 3
    assert all(call.endswith(' --dry-run') for call in calls)
    assert calls[0] == 'scripts/ci/ingest_pr_knowledge.py --pr-num 917 --dry-run'
    assert 'nothing is stored, reviewed, or approved' in summary
    assert 'summary-md' not in workflow_step()
    assert 'SUPABASE_SERVICE_ROLE_KEY' not in WORKFLOW.read_text().split('  sync-collective-ai-knowledge:', 1)[1]


@pytest.mark.parametrize('failure', ['ingest_pr_knowledge.py', '--share-json', '--scan-issue'])
def test_validation_errors_fail_job(tmp_path, failure):
    result, _, _ = invoke(tmp_path, subject='change (#917)', share='{}', issue='45', fail_on=failure)
    assert result.returncode == 7


def test_non_pr_push_does_not_attempt_ingestion(tmp_path):
    result, calls, _ = invoke(tmp_path, subject='ordinary commit')
    assert result.returncode == 0
    assert calls == []
