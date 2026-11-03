"""Fail-closed contract tests for scripts/deploy/generate_firebase_config.py.

BACKGROUND (2026-09-18 live incident, False-Assurance doctrine): the generator
used to REQUIRE three API rewrites (/api/**, /api/v1/**, /admin-api/**) whose
destinations pointed at the backend origin. Deep verification against real
production proved that contract was architecturally impossible: Firebase
Hosting rewrites only proxy to local files / Cloud Functions / Cloud Run —
official docs define rewrite `destination` as "a local file that must exist",
and external-origin proxying silently 404s every /api/* path at the edge while
looking fully configured. The repo's own frontend (utils/api.ts) already calls
the API origin directly with CORS. The generator's contract is now:

1. The SPA fallback (** -> /index.html) must exist on every hosting site.
2. Any rewrite destination that is an absolute URL is a lying artifact —
   fail-closed rejection (external proxying is unsupported).
3. BACKEND_URL is optional (placeholder-free template), but if set and it
   points at a Firebase Hosting domain (*.web.app / *.firebaseapp.com),
   that is a hosting-site-as-API-origin misconfiguration — fail-closed.
4. All previous fail-fast checks (missing template, unresolved placeholders,
   invalid JSON) are preserved; generation is deterministic.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
SCRIPT_PATH = REPO_ROOT / "scripts" / "deploy" / "generate_firebase_config.py"

_spec = importlib.util.spec_from_file_location("generate_firebase_config", SCRIPT_PATH)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)

BACKEND_URL = "https://api.example.com"


def _template(
    *,
    sources: tuple[str, ...] = ("**",),
    destinations: dict[str, str] | None = None,
    spa_destination: str = "/index.html",
    shape: str = "list",
) -> str:
    dests = {"**": spa_destination, **(destinations or {})}
    rewrites = [{"source": s, "destination": dests[s]} for s in sources if s in dests]
    site = {
        "target": "user",
        "public": "frontend/dist",
        "rewrites": rewrites,
    }
    doc = {"hosting": [site, {**site, "target": "admin"}] if shape == "list" else site}
    return json.dumps(doc)


def _run_generate(monkeypatch, tmp_path: Path, template: str | None, env_url: str | None = None):
    monkeypatch.chdir(tmp_path)
    if template is not None:
        (tmp_path / "firebase.template.json").write_text(template, encoding="utf-8")
    for var in (
        "BACKEND_URL",
        "VITE_BACKEND_URL",
        "VITE_API_URL",
        "USER_BACKEND_URL",
        "VITE_USER_BACKEND",
    ):
        monkeypatch.delenv(var, raising=False)
    if env_url is not None:
        monkeypatch.setenv("BACKEND_URL", env_url)
    gen.generate_firebase_config()


# ---------------------------------------------------------------------------
# Happy paths
# ---------------------------------------------------------------------------


def test_real_repo_template_passes_end_to_end(monkeypatch, tmp_path):
    """The ACTUAL committed template must satisfy the fail-closed contract."""
    real_template = (REPO_ROOT / "firebase.template.json").read_text(encoding="utf-8")
    out_dir = tmp_path / "repo"
    out_dir.mkdir()
    (out_dir / "firebase.template.json").write_text(real_template, encoding="utf-8")
    monkeypatch.chdir(out_dir)
    monkeypatch.setenv("BACKEND_URL", BACKEND_URL)
    gen.generate_firebase_config()
    produced = json.loads((out_dir / "firebase.json").read_text(encoding="utf-8"))
    sites = produced["hosting"]
    assert {s["target"] for s in sites} == {"user", "admin"}
    for site in sites:
        # বাংলা: চুক্তি — কেবল SPA fallback; কোনো /api rewrite নেই (অসম্ভব স্তর)।
        srcs = {rw["source"] for rw in site["rewrites"]}
        assert srcs == {"**"}
        assert site["rewrites"][0]["destination"] == "/index.html"

        # বাংলা: সিকিউরিটি হেডার যাচাই — CSP উপস্থিত ও X-XSS-Protection অনুপস্থিত
        headers_by_key = {
            h["key"].lower(): h["value"]
            for h_rule in site.get("headers", [])
            for h in h_rule.get("headers", [])
        }
        assert "content-security-policy" in headers_by_key
        assert "x-xss-protection" not in headers_by_key


def test_minimal_valid_template_generates_output(monkeypatch, tmp_path):
    _run_generate(monkeypatch, tmp_path, _template())
    produced = json.loads((tmp_path / "firebase.json").read_text(encoding="utf-8"))
    rewrites = produced["hosting"][0]["rewrites"]
    assert rewrites == [{"source": "**", "destination": "/index.html"}]


def test_generation_is_deterministic(monkeypatch, tmp_path):
    _run_generate(monkeypatch, tmp_path, _template())
    first = (tmp_path / "firebase.json").read_bytes()
    (tmp_path / "firebase.json").unlink()
    _run_generate(monkeypatch, tmp_path, _template())
    assert (tmp_path / "firebase.json").read_bytes() == first


def test_generation_works_without_backend_url(monkeypatch, tmp_path):
    """Placeholder-free template: BACKEND_URL absence must not fail the deploy.

    বাংলা: পুরোনো চুক্তিতে BACKEND_URL ছিল আবশ্যক (rewrite substitution-এর জন্য);
    নতুন SPA-fallback-only চুক্তিতে placeholder নেই — env ছাড়াই deterministic
    আউটপুট হবে। এটি সততার প্রমাণ: অপ্রয়োজনীয় কনফিগ আর বাধ্যতামূলক নয়।
    """
    _run_generate(monkeypatch, tmp_path, _template(), env_url=None)
    assert (tmp_path / "firebase.json").exists()


def test_dict_hosting_shape_still_validated(monkeypatch, tmp_path):
    _run_generate(monkeypatch, tmp_path, _template(shape="dict"))
    assert (tmp_path / "firebase.json").exists()


# ---------------------------------------------------------------------------
# Template fail-fast (pre-existing contract, still enforced)
# ---------------------------------------------------------------------------


def test_missing_template_exits(monkeypatch, tmp_path):
    with pytest.raises(SystemExit) as exc:
        _run_generate(monkeypatch, tmp_path, None)
    assert exc.value.code == 1


def test_unresolved_placeholders_exits(monkeypatch, tmp_path):
    template = _template().replace("frontend/dist", "frontend/dist/{{UNKNOWN}}")
    with pytest.raises(SystemExit) as exc:
        _run_generate(monkeypatch, tmp_path, template)
    assert exc.value.code == 1


def test_invalid_json_exits(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "firebase.template.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as exc:
        gen.generate_firebase_config()
    assert exc.value.code == 1


# ---------------------------------------------------------------------------
# Rewrite honesty contract (2026-09-18 incident — fail-closed)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    ["/api/**", "/api/v1/**", "/admin-api/**"],
    ids=["api", "api-v1", "admin-api"],
)
def test_external_url_rewrite_destination_rejected(monkeypatch, tmp_path, source, capsys):
    """An absolute-URL rewrite destination is an impossible proxy — reject it.

    বাংলা: Firebase Hosting external-origin proxy করে না; এমন এন্ট্রি থাকা
    মানে configured দেখায় কিন্তু প্রতিটি ম্যাচিং পাথে নীরবে 404 দেয়
    (2026-09-18 লাইভ ইনসিডেন্ট) — তাই fail-closed।
    """
    template = _template(
        sources=(source, "**"),
        destinations={source: f"{BACKEND_URL}{source}"},
    )
    with pytest.raises(SystemExit) as exc:
        _run_generate(monkeypatch, tmp_path, template)
    assert exc.value.code == 1
    out = capsys.readouterr().out
    assert "absolute URL" in out
    assert "not supported by Firebase Hosting rewrites" in out


def test_hosting_domain_backend_url_rejected(monkeypatch, tmp_path, capsys):
    """BACKEND_URL pointing at a hosting site is never an API origin.

    বাংলা: Hosting ডোমেন API origin নয় — এই ভুল মান নীরবে ডিপ্লয় হতে
    পারবে না (2026-09-18 ইনসিডেন্ট: secret একটি Hosting ডোমেনে পয়েন্ট করা ছিল)।
    """
    for host in ("supremeai-a.web.app", "supremeai-a.firebaseapp.com"):
        with pytest.raises(SystemExit) as exc:
            _run_generate(monkeypatch, tmp_path, _template(), env_url=f"https://{host}")
        assert exc.value.code == 1, host
        out = capsys.readouterr().out
        assert "Firebase Hosting domain" in out


def test_missing_spa_fallback_rejected(monkeypatch, tmp_path, capsys):
    template = _template(sources=())
    with pytest.raises(SystemExit) as exc:
        _run_generate(monkeypatch, tmp_path, template)
    assert exc.value.code == 1
    assert "SPA fallback" in capsys.readouterr().out


def test_wrong_spa_destination_rejected(monkeypatch, tmp_path):
    template = _template(spa_destination="/app.html")
    with pytest.raises(SystemExit) as exc:
        _run_generate(monkeypatch, tmp_path, template)
    assert exc.value.code == 1


def test_deprecated_xss_protection_rejected(monkeypatch, tmp_path, capsys):
    site = {
        "target": "user",
        "public": "frontend/dist",
        "rewrites": [{"source": "**", "destination": "/index.html"}],
        "headers": [
            {
                "source": "**",
                "headers": [
                    {"key": "Content-Security-Policy", "value": "default-src 'self'"},
                    {"key": "X-XSS-Protection", "value": "1; mode=block"},
                ],
            }
        ],
    }
    template = json.dumps({"hosting": [site]})
    with pytest.raises(SystemExit) as exc:
        _run_generate(monkeypatch, tmp_path, template)
    assert exc.value.code == 1
    assert "deprecated header X-XSS-Protection" in capsys.readouterr().out


def test_missing_csp_rejected_when_headers_present(monkeypatch, tmp_path, capsys):
    site = {
        "target": "user",
        "public": "frontend/dist",
        "rewrites": [{"source": "**", "destination": "/index.html"}],
        "headers": [
            {
                "source": "**",
                "headers": [
                    {"key": "X-Content-Type-Options", "value": "nosniff"},
                ],
            }
        ],
    }
    template = json.dumps({"hosting": [site]})
    with pytest.raises(SystemExit) as exc:
        _run_generate(monkeypatch, tmp_path, template)
    assert exc.value.code == 1
    assert "missing Content-Security-Policy header" in capsys.readouterr().out


def test_require_build_checks_artifact(monkeypatch, tmp_path, capsys):
    out_dir = tmp_path / "repo"
    out_dir.mkdir()
    (out_dir / "firebase.template.json").write_text(_template(), encoding="utf-8")
    monkeypatch.chdir(out_dir)

    # When artifact is missing
    with pytest.raises(SystemExit) as exc:
        gen.generate_firebase_config(require_build=True)
    assert exc.value.code == 1
    assert "Frontend build artifact missing or empty" in capsys.readouterr().out

    # When artifact is present
    dist_dir = out_dir / "frontend" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<!DOCTYPE html><html></html>", encoding="utf-8")

    gen.generate_firebase_config(require_build=True)
    assert (out_dir / "firebase.json").exists()
