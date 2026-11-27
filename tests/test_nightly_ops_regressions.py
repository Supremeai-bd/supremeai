from __future__ import annotations

from pathlib import Path

import yaml

from scripts.advanced_analysis import ai_memory_integrity_audit
from scripts.quality import self_audit_scan
from scripts.ops import detect_silent_errors

ROOT = Path(__file__).resolve().parents[1]


def test_self_audit_honors_python_encoding_and_detects_invalid_syntax(tmp_path):
    (tmp_path / "bom.py").write_bytes(b"\xef\xbb\xbfvalue = 1\n")
    (tmp_path / "latin.py").write_bytes(b"# coding: latin-1\nname = '\xe9'\n")
    (tmp_path / "broken.py").write_text("def broken(:\n", encoding="utf-8")
    result = self_audit_scan.scan_python(tmp_path)
    assert len(result["syntax_errors"]) == 1
    assert result["syntax_errors"][0].startswith("broken.py:")


def test_silent_error_scanner_honors_bom_and_detects_real_syntax(tmp_path):
    bom = tmp_path / "bom.py"
    bom.write_bytes(b"\xef\xbb\xbfvalue = 1\n")
    assert detect_silent_errors.scan_python_file(str(bom), True) == []
    broken = tmp_path / "broken.py"
    broken.write_text("def broken(:\n", encoding="utf-8")
    findings = detect_silent_errors.scan_python_file(str(broken), True)
    assert any(item["type"] == "syntax-error" for item in findings)


def test_self_audit_reports_invalid_source_encoding(tmp_path):
    (tmp_path / "bad.py").write_bytes(b"# coding: imaginary-codec\nvalue=1\n")
    assert len(self_audit_scan.scan_python(tmp_path)["syntax_errors"]) == 1


def test_memory_integrity_checks_actual_core_service(monkeypatch, tmp_path):
    assert ai_memory_integrity_audit.BACKEND_ROOT == ROOT / "core"
    assert ai_memory_integrity_audit.audit_memory_service_implementation() == []
    monkeypatch.setattr(ai_memory_integrity_audit, "BACKEND_ROOT", tmp_path)
    assert "Missing memory service" in ai_memory_integrity_audit.audit_memory_service_implementation()[0]


def test_local_composite_actions_have_checkout_first():
    workflow = yaml.safe_load((ROOT / ".github/workflows/ops-maintenance.yml").read_text(encoding="utf-8"))
    for job_name, job in workflow["jobs"].items():
        checked_out = False
        for step in job.get("steps", []):
            uses = step.get("uses", "")
            if uses.startswith("actions/checkout@"):
                checked_out = True
            if uses.startswith("./"):
                assert checked_out, f"{job_name}: local action {uses} before checkout"


def test_nightly_load_and_security_checks_do_not_claim_unrun_scans():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ops-maintenance.yml').read_text(encoding='utf-8'))
    jobs = workflow['jobs']
    locust = jobs['load-locust']['steps']
    require = next(step['run'] for step in locust if step.get('id') == 'target')
    assert 'exit 1' in require and 'skip=true' not in require
    garak = '\n'.join(step.get('run', '') for step in jobs['garak-redteam']['steps'])
    assert 'live red-team scan NOT RUN' in garak
    dast = jobs['dast-zap']['steps'] if 'dast-zap' in jobs else next(j['steps'] for j in jobs.values() if any('zaproxy/action-api-scan@' in s.get('uses', '') for s in j.get('steps', [])))
    api = next(s for s in dast if 'zaproxy/action-api-scan@' in s.get('uses', ''))['with']
    assert api['target'] == 'core/API-swagger.yaml'
    assert api['cmd_options'] == '-O ${{ env.ZAP_TARGET }}'
    assert api['fail_action'] is True and 'spec' not in api


def test_nightly_points_to_current_suites_and_registry():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ops-maintenance.yml').read_text(encoding='utf-8'))
    jobs = workflow['jobs']
    chaos = next(s for s in jobs['chaos-suite']['steps'] if s.get('name') == 'Run chaos-marked tests')
    assert chaos['working-directory'] == './core'
    assert 'pytest tests/chaos' in chaos['run']
    assert (ROOT / 'core/tests/chaos').is_dir()
    assert 'guard_inventory.py --check' in jobs['run-guards-registry-check']['steps'][-1]['run']
    assert 'exit 1' in next(s['run'] for s in jobs['browser-e2e']['steps'] if s.get('name') == 'Require real-browser test suite')


def test_mission_harness_rejects_partial_xml_on_infrastructure_error(monkeypatch, tmp_path):
    from scripts.ci import mission_passk
    import pytest

    monkeypatch.setattr(mission_passk, 'CORE_DIR', tmp_path)
    (tmp_path / 'mission_junit_1.xml').write_text('<testsuite tests="1"/>')

    class FakeProcess:
        returncode = 2
        def communicate(self, timeout):
            assert not (tmp_path / 'mission_junit_1.xml').exists()
            (tmp_path / 'mission_junit_1.xml').write_text('<testsuite tests="1"/>')
            return ('collection failed', '')

    monkeypatch.setattr(mission_passk.subprocess, 'Popen', lambda *args, **kwargs: FakeProcess())
    with pytest.raises(SystemExit) as exc:
        mission_passk.run_mission_suite(1)
    assert exc.value.code == 2
    assert not (tmp_path / 'mission_junit_1.xml').exists()
    assert mission_passk.MISSION_DIR == 'tests/missions'


def test_mission_gate_counts_same_tests_passing_every_run(monkeypatch, tmp_path):
    import json
    import sys
    from scripts.ci import mission_passk

    all_ids = frozenset({('module', 'a'), ('module', 'b')})
    outcomes = iter([
        (1, 2, all_ids, frozenset({('module', 'a')})),
        (1, 2, all_ids, frozenset({('module', 'b')})),
    ])
    monkeypatch.setattr(mission_passk, 'run_mission_suite', lambda _: next(outcomes))
    monkeypatch.setattr(mission_passk, 'REPORT_DIR', tmp_path)
    monkeypatch.setattr(sys, 'argv', ['mission_passk', '--k', '2', '--min-pass-hat-k', '0.1'])
    assert mission_passk.main() == 1
    report = json.loads((tmp_path / 'mission_passk.json').read_text())
    assert report['successes_all_runs'] == 0
    assert report['pass_hat_k'] == 0


def test_mission_gate_rejects_changed_test_identity(monkeypatch, tmp_path):
    import sys
    import pytest
    from scripts.ci import mission_passk
    first = frozenset({('module', 'a')})
    second = frozenset({('module', 'b')})
    outcomes = iter([(1, 1, first, first), (1, 1, second, second)])
    monkeypatch.setattr(mission_passk, 'run_mission_suite', lambda _: next(outcomes))
    monkeypatch.setattr(mission_passk, 'REPORT_DIR', tmp_path)
    (tmp_path / 'mission_passk.json').write_text('stale')
    monkeypatch.setattr(sys, 'argv', ['mission_passk', '--k', '2'])
    with pytest.raises(SystemExit) as exc:
        mission_passk.main()
    assert exc.value.code == 2
    assert not (tmp_path / 'mission_passk.json').exists()


def test_zap_is_disabled_until_authorized_staging_exists():
    workflow = yaml.safe_load((ROOT / '.github/workflows/ops-maintenance.yml').read_text(encoding='utf-8'))
    dast = workflow['jobs']['dast']
    # Applies to both scheduled runs and manual dispatch, including run_all.
    assert dast['if'] is False
    assert dast['env']['ZAP_TARGET'] == '${{ vars.STAGING_BASE_URL }}'
    assert any(s.get('name') == 'Require scan target' and 'exit 1' in s['run'] for s in dast['steps'])
    assert any(s.get('name') == 'Validate authorized staging target syntax' for s in dast['steps'])
