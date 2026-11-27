from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from scripts.ops import zap_passive_production as scan


@pytest.mark.parametrize("bad", ["", "http://example.com", "https://example.com/path", "https://example.com/?a=1", "https://user:pass@example.com", "https://127.0.0.1", "https://localhost", "https://example.com:bad", "https://example.com,https://other.com"])
def test_reject_invalid_or_unsafe_target(bad):
    with pytest.raises(ValueError):
        scan.validate_origin(bad)


def test_https_origin_normalized():
    assert scan.validate_origin("https://EXAMPLE.COM:443/") == "https://example.com:443/"


def test_only_proxy_get_without_redirects_or_credentials():
    class Result:
        stdout = "200"
    with patch.object(scan.subprocess, "run", return_value=Result()) as run:
        assert scan.request("https://example.com/", True) == 200
    args = run.call_args.args[0]
    assert args[-1] == "https://example.com/"
    assert "--proxy" in args and "--noproxy" in args
    assert "Origin: https://zap-test.invalid" in args
    assert "--location" not in args and "--data" not in args and "--user" not in args


def test_workflow_is_manual_passive_and_full_scan_staging_only():
    root = Path(__file__).resolve().parents[1]
    jobs = yaml.safe_load((root / '.github/workflows/ops-maintenance.yml').read_text())['jobs']
    assert jobs['dast']['if'] is False
    assert jobs['dast']['env']['ZAP_TARGET'] == '${{ vars.STAGING_BASE_URL }}'
    job = jobs['production-passive-baseline']
    cond = job['if']
    assert "github.event_name == 'workflow_dispatch'" in cond and 'inputs.run_dast == true' in cond
    assert "github.ref != 'refs/heads/main'" in cond and 'inputs.run_all != true' in cond
    assert all('zaproxy/action-full-scan' not in s.get('uses', '') and 'zaproxy/action-api-scan' not in s.get('uses', '') for s in job['steps'])
