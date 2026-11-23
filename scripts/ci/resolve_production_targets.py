#!/usr/bin/env python3
"""Canonical production target resolution (issue #1132 — single contract).

বাংলা নীতি: প্রতিটি production smoke workflow (qa-live-smoke, 09-post-deploy-smoke,
release certification) একই resolver ব্যবহার করবে — একই deployment সব স্মোকে একই
UI/API target + provenance দেখাবে। আলাদা আলাদা inline চেইন = আলাদা আলাদা সত্য,
যা release certification-কে মিথ্যা বিভ্রান্তি দেয়।

Resolution contract (the ONLY one — owner overrides preserved, zero-hardcode):

UI origin (browser-facing SPA surface):
  1. FRONTEND_PRODUCTION_URL (secret, owner override) → "FRONTEND_PRODUCTION_URL (owner override)"
  2. FIREBASE_PROJECT_ID → https://{project}.web.app   → "FIREBASE_PROJECT_ID-derived ({p}.web.app) — SPA hosting"
  3. none                                             → "" (UNVERIFIED — fail-closed, never fabricated)

API origin (backend service surface):
  1. PRODUCTION_URL (var || secret, owner override)    → "PRODUCTION_URL (owner override)"
  2. RENDER_CORE_URL (Infisical prod)                  → "RENDER_CORE_URL (Infisical prod)"
  3. UI-origin same-origin fallback (ONLY when UI known)→ "same-origin fallback (UI origin; rewrite chain is the API path)"
  4. none                                             → "" (UNVERIFIED — fail-closed)

backend_health_url == API origin (post-deploy health probe consumes the same truth).
qa_base_url == UI origin (Playwright canary consumes the frontend surface).

Rules:
- Values are rstrip("/"-normalized; empty stays empty — NO localhost/placeholder
  fabrication (unresolved targets must remain UNVERIFIED, fail-closed).
- UI and API surfaces resolve INDEPENDENTLY: Firebase-hosted SPA + Render API is
  two distinct origins by design (Firebase Hosting cannot proxy external origins).
- A PRODUCTION_URL pointing at a Firebase hosting domain (*.web.app /
  *.firebaseapp.com) is the 2026-09-18 live-incident misconfiguration — resolved
  (owner override wins) but flagged loudly in `notes` so provenance stays honest.
- Stdlib-only; exit 0 always — enforcement (fail-closed "Require target" steps)
  belongs to the calling workflow; this script only resolves + reports provenance.

Usage:
    python3 scripts/ci/resolve_production_targets.py --env-file "$GITHUB_ENV"

Env inputs (as passed by the workflows):
    EXPLICIT_URL / PRODUCTION_URL   API owner override (PRODUCTION_URL preferred)
    FRONTEND_EXPLICIT_URL           UI owner override (FRONTEND_PRODUCTION_URL)
    FIREBASE_PROJECT                Firebase project id
    RENDER_CORE                     Infisical RENDER_CORE_URL — may hold a
                                    comma-separated candidate list; the first
                                    candidate whose /api/v1/health/live returns
                                    200+status JSON wins (live-verified)
    RESOLVER_SKIP_VERIFY            set to 1 to skip network verification
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

HOSTING_DOMAIN_SUFFIXES = (".web.app", ".firebaseapp.com")

ENV_KEYS = (
    "UI_ORIGIN",
    "UI_ORIGIN_SOURCE",
    "API_ORIGIN",
    "API_ORIGIN_SOURCE",
    "BACKEND_HEALTH_URL",
    "BACKEND_HEALTH_SOURCE",
    "QA_BASE_URL",
)

# Live-verification probe contract (2026-11-24 fix-pack addendum).
# RENDER_CORE_URL (and PRODUCTION_URL overrides via comma-list) may hold a
# comma-separated CANDIDATE list. The resolver probes each candidate's
# /api/v1/health/live and picks the FIRST candidate that honestly answers
# 200 + JSON with a "status" key. Rationale (2026-11-23 nightly incident):
# Infisical RENDER_CORE_URL pointed at the retired gateway (supremeai-api-ulw0)
# which answers 404 for /api/v1/health/* — live-smoke (fail-closed) burned red
# for days while the real core (supremeai-primary-node-5xso) was healthy.
# A candidate list lets the owner fix config in one edit WITHOUT losing the
# zero-hardcode doctrine: candidates come only from owner-owned config, and
# provenance always reports what was probed and what won.
HEALTH_PROBE_PATH = "/api/v1/health/live"
HEALTH_PROBE_TIMEOUT_S = 8
RESOLVER_VERIFY_ENV = "RESOLVER_SKIP_VERIFY"  # set to 1/true to probe offline


def _clean(value: str | None) -> str:
    return (value or "").strip().rstrip("/")


def _verify_api_candidate(url: str) -> tuple[bool, str]:
    """Stdlib live probe of {url}/api/v1/health/live → (verified, detail).

    Verified = HTTP 200 + parseable JSON containing a "status" key (the same
    contract live-smoke's Layer B asserts). Network errors/404/5xx ⇒ False.
    Never raises — verification is advisory, fail-closed enforcement stays
    with the calling workflow."""
    try:
        req = urllib.request.Request(
            url.rstrip("/") + HEALTH_PROBE_PATH,
            headers={"User-Agent": "supremeai-target-resolver"},
        )
        with urllib.request.urlopen(req, timeout=HEALTH_PROBE_TIMEOUT_S) as resp:
            body = resp.read()
            code = resp.status
        if code != 200:
            return False, f"HTTP {code}"
        try:
            data = json.loads(body.decode("utf-8", errors="replace"))
        except Exception:  # noqa: BLE001 — non-JSON = contract broken
            return False, "HTTP 200 but non-JSON body"
        if not isinstance(data, dict) or "status" not in data:
            return False, "HTTP 200 JSON without 'status' key"
        return True, "HTTP 200 JSON status ✓"
    except Exception as exc:  # noqa: BLE001 — any network failure is a verdict
        return False, f"{type(exc).__name__}: {exc}"


def resolve_targets(
    *,
    api_explicit: str = "",
    ui_explicit: str = "",
    firebase_project: str = "",
    render_core: str = "",
) -> tuple[dict[str, str], list[str]]:
    """Resolve UI/API production targets; return (env_lines, notes).

    env_lines maps the contract keys above (already normalized); notes carries
    human-readable provenance advisories (never secret values).
    """
    api_explicit = _clean(api_explicit)
    ui_explicit = _clean(ui_explicit)
    firebase_project = (firebase_project or "").strip()
    render_core = _clean(render_core)

    notes: list[str] = []

    # --- UI origin (independent surface) ---
    if ui_explicit:
        ui_origin = ui_explicit
        ui_src = "FRONTEND_PRODUCTION_URL (owner override)"
    elif firebase_project:
        ui_origin = f"https://{firebase_project}.web.app"
        ui_src = (
            f"FIREBASE_PROJECT_ID-derived ({firebase_project}.web.app) — SPA hosting"
        )
    else:
        ui_origin, ui_src = "", ""

    # --- API origin (independent surface) ---
    if api_explicit:
        api_origin = api_explicit
        api_src = "PRODUCTION_URL (owner override)"
        # বাংলা: 2026-09-18 live incident — hosting domain-কে API origin ভাবা।
        # Override সম্মান করা হয়, কিন্তু provenance-এ জোরে ফ্ল্যাগ করা হয়।
        if any(api_origin.endswith(s) for s in HOSTING_DOMAIN_SUFFIXES):
            notes.append(
                "MISCONFIGURATION WARNING: PRODUCTION_URL override points at a "
                "Firebase Hosting domain — that surface serves the SPA, not the "
                "API (rewrites cannot proxy external origins). Same-origin "
                "assumptions will misprobe; verify the API origin."
            )
        if not firebase_project and not ui_explicit:
            notes.append(
                "PRODUCTION_URL override set, but no FRONTEND_PRODUCTION_URL / "
                "FIREBASE_PROJECT_ID — SPA origin not derivable; Layer A SPA row "
                "will be UNVERIFIED."
            )
    elif render_core:
        # 2026-11-24 addendum: comma-separated candidates are live-verified and
        # the first honest /api/v1/health/live winner becomes the API origin.
        candidates = [c.strip().rstrip("/") for c in render_core.split(",") if c.strip()]
        if len(candidates) > 1:
            skip_verify = os.environ.get(RESOLVER_VERIFY_ENV, "").strip().lower() in ("1", "true", "yes")
            if skip_verify:
                api_origin = candidates[0]
                api_src = ("RENDER_CORE_URL (Infisical prod) — candidate[0] "
                           f"of {len(candidates)} (verification skipped)")
                notes.append(
                    f"RENDER_CORE_URL held {len(candidates)} candidates; "
                    f"RESOLVER_SKIP_VERIFY=1 → picked candidate[0] without probing."
                )
            else:
                probed: list[str] = []
                chosen: str | None = None
                for cand in candidates:
                    ok, detail = _verify_api_candidate(cand)
                    probed.append(f"{cand} → {detail}")
                    if ok and chosen is None:
                        chosen = cand
                if chosen:
                    api_origin = chosen
                    api_src = ("RENDER_CORE_URL (Infisical prod) — live-verified "
                               f"winner of {len(candidates)} candidates via "
                               f"{HEALTH_PROBE_PATH}")
                else:
                    # Honest fallback: keep candidate[0] so fail-closed callers
                    # still probe SOMETHING, but flag loudly that nothing won.
                    api_origin = candidates[0]
                    api_src = "RENDER_CORE_URL (Infisical prod) — candidate[0] fallback (NONE verified)"
                    notes.append(
                        "MISCONFIGURATION WARNING: no RENDER_CORE_URL candidate "
                        f"answered {HEALTH_PROBE_PATH} with 200+status JSON — "
                        "API rows will probe candidate[0] and likely FAIL; fix "
                        "Infisical RENDER_CORE_URL (2026-11 migration: new core "
                        "= supremeai-primary-node-5xso.onrender.com)."
                    )
                notes.append("Candidate probe ledger: " + " | ".join(probed))
        else:
            api_origin = render_core
            api_src = "RENDER_CORE_URL (Infisical prod)"
            # Single-candidate honesty probe (2026-11-23 incident: retired
            # gateway 404s /api/v1/health/* while the nightly burns red).
            if os.environ.get(RESOLVER_VERIFY_ENV, "").strip().lower() not in ("1", "true", "yes"):
                ok, detail = _verify_api_candidate(api_origin)
                if not ok:
                    notes.append(
                        f"RENDER_CORE_URL candidate did NOT verify on "
                        f"{HEALTH_PROBE_PATH} ({detail}) — if this is the retired "
                        "gateway (supremeai-api-ulw0), the 2026-11 core migration "
                        "moved the API to supremeai-primary-node-5xso.onrender.com; "
                        "update Infisical RENDER_CORE_URL (or set a comma-separated "
                        "candidate list; the resolver picks the live winner)."
                    )
    elif ui_origin:
        api_origin = ui_origin
        api_src = "same-origin fallback (UI origin; rewrite chain is the API path)"
        notes.append(
            "API origin fell back to the UI origin (same-origin deployment). "
            "If the SPA and API actually live on separate origins, set "
            "vars.PRODUCTION_URL or Infisical RENDER_CORE_URL explicitly."
        )
    else:
        api_origin, api_src = "", ""
        notes.append(
            "No API target resolvable (PRODUCTION_URL / RENDER_CORE_URL / UI "
            "origin all unset) — API rows will be UNVERIFIED (fail-closed)."
        )

    env_lines = {
        "UI_ORIGIN": ui_origin,
        "UI_ORIGIN_SOURCE": ui_src,
        "API_ORIGIN": api_origin,
        "API_ORIGIN_SOURCE": api_src,
        "BACKEND_HEALTH_URL": api_origin,
        "BACKEND_HEALTH_SOURCE": api_src,
        "QA_BASE_URL": ui_origin,
    }
    return env_lines, notes


def _read_env_inputs() -> dict[str, str]:
    return {
        "api_explicit": os.environ.get("PRODUCTION_URL")
        or os.environ.get("EXPLICIT_URL", ""),
        "ui_explicit": os.environ.get("FRONTEND_EXPLICIT_URL", ""),
        "firebase_project": os.environ.get("FIREBASE_PROJECT", ""),
        "render_core": os.environ.get("RENDER_CORE", ""),
    }


def _print_provenance(env_lines: dict[str, str], notes: list[str]) -> None:
    print("Production target resolution (canonical contract, #1132):")
    for surface, url_key, src_key in (
        ("UI", "UI_ORIGIN", "UI_ORIGIN_SOURCE"),
        ("API", "API_ORIGIN", "API_ORIGIN_SOURCE"),
    ):
        url, src = env_lines[url_key], env_lines[src_key]
        print(f"  {surface}: {url or '(none)'}  source={src or '-'}")
    for note in notes:
        print(f"  note: {note}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--env-file",
        default="",
        help="append KEY=VALUE lines to this file (e.g. $GITHUB_ENV); "
        "provenance always prints to stdout",
    )
    args = parser.parse_args(argv)

    env_lines, notes = resolve_targets(**_read_env_inputs())
    _print_provenance(env_lines, notes)

    if args.env_file:
        with open(args.env_file, "a", encoding="utf-8") as fh:
            fh.writelines(f"{key}={env_lines[key]}\n" for key in ENV_KEYS)
    else:
        for key in ENV_KEYS:
            print(f"{key}={env_lines[key]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
