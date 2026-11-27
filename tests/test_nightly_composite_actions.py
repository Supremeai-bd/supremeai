"""Composite smoke checks exercise fake responses only; no live calls."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('mode,all_targets,expected', [
    ('success', True, 'PASS'),
    ('success', False, 'FAIL'),
    ('network-error', True, 'FAIL'),
])
def test_live_smoke_never_certifies_unverified_or_unreachable(tmp_path, mode, all_targets, expected):
    action = yaml.safe_load((ROOT / '.github/actions/live-smoke/action.yml').read_text())
    script = next(step['run'] for step in action['runs']['steps'] if step.get('name', '').startswith('Probe live chain'))
    (tmp_path / 'sitecustomize.py').write_text('''
import io, json, os, time, urllib.request

time.sleep = lambda *_: None
class Response:
    status = 200
    headers = {"Access-Control-Allow-Origin": "https://ui.example"}
    def __enter__(self): return self
    def __exit__(self, *args): pass
    def read(self):
        if self.url.endswith("/"): return b"<!doctype html><html></html>"
        return json.dumps({"status": "ok", "plans": {}}).encode()
def fake_open(request, **kwargs):
    if os.environ["FAKE_MODE"] == "network-error": raise OSError("network unavailable")
    result = Response()
    result.url = request.full_url
    return result
urllib.request.urlopen = fake_open
''', encoding='utf-8')
    env = {**os.environ, 'PYTHONPATH': str(tmp_path), 'FAKE_MODE': mode,
           'UI_ORIGIN': 'https://ui.example', 'API_ORIGIN': 'https://api.example',
           'CI_REPORTS_DIR': str(tmp_path / 'reports'), 'GITHUB_STEP_SUMMARY': str(tmp_path / 'summary')}
    for key in ('RENDER_WORKER_URL', 'RENDER_SCRAPER_URL', 'RENDER_MCP_URL'):
        env[key] = 'https://service.example' if all_targets else ''
    completed = subprocess.run(['bash', '-c', script], env=env, capture_output=True, text=True, timeout=10)
    cert = json.loads((tmp_path / 'reports/production-certification.json').read_text())
    assert cert['verdict'] == expected, completed.stdout + completed.stderr
    assert (completed.returncode == 0) == (expected == 'PASS')
    if mode == 'network-error':
        assert cert['summary']['fail'] > 0
    if not all_targets:
        assert cert['summary']['unverified'] == 3


def test_full_audit_root_resolves_to_repository():
    script = (ROOT / 'scripts/ops/ci-full-audit.sh').read_text()
    assert '$(dirname "${BASH_SOURCE[0]}")/../..' in script


def test_customer_e2e_fails_closed_when_surface_or_credentials_missing():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ops-maintenance.yml').read_text())
    steps = workflow['jobs']['e2e-customer']['steps']
    surface = next(s for s in steps if s.get('name') == 'Require customer E2E test surface')
    assert 'qa/playwright.config.qa.ts' in surface['run'] and 'exit 1' in surface['run']
    auth = next(s for s in steps if s.get('id') == 'auth_check')
    assert 'QA_CUSTOMER_EMAIL' in auth['run'] and 'QA_CUSTOMER_PASSWORD' in auth['run']
    assert 'exit 1' in auth['run'] and 'skip=true' not in auth['run']
    target = next(s for s in steps if s.get('id') == 'target')
    assert 'exit 1' in target['run'] and 'retired-skip' not in target['run']


def test_roster_preserves_process_exit_and_surfaces_failures():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ops-maintenance.yml').read_text())
    steps = next(job['steps'] for job in workflow['jobs'].values() if any(s.get('name') == 'Run every guard' for s in job.get('steps', [])))
    run = next(s['run'] for s in steps if s.get('name') == 'Run every guard')
    assert 'roster_rc=$?' in run and '[ "$roster_rc" -ne 0 ]' in run
    assert 'named failures' in run


def test_dependency_scan_uses_studio_package_manager_not_a_hardcoded_version():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ops-maintenance.yml').read_text())
    steps = workflow['jobs']['dependency-scan']['steps']
    setup = next(step for step in steps if step.get('uses', '').startswith('pnpm/action-setup@'))
    assert setup['if'] == "steps.check_studio.outputs.present == 'true'"
    assert setup['with']['package_json_file'] == 'studio/package.json'
    assert 'version' not in setup['with']
