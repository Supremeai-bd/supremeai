#!/usr/bin/env python3
"""Mesh-wide Render release parity gate (audit F3, 2026-11-25).

The post-merge deploy matrix (`deploy-render-services`) is path-scoped: only
services whose `watch_paths` changed get deployed and attested. A commit that
touches a single service therefore leaves every sibling on an older release
SHA — the exact drift observed on 2026-11-25 (api at 98d8cd88 while core,
worker, scraper and brain stayed on 918fee5e). Each leg is individually
"verified", so nothing catches the mesh falling apart.

This gate re-derives, from the canonical service registry
(`config/service_registry.yaml`), the commit each Render service's watch_paths
LAST expected, then asks the Render API for the service's current live deploy
commit. A service passes iff its live commit is the expected commit or a
descendant of it (deployed ahead is fine). Anything else — stale commit,
no live deploy, missing commit evidence, API failure — is a blocking entry.

Fail-closed by default. Set MESH_PARITY_FAIL_OPEN=1 (repo variable) to downgrade
every entry to a warning during the one-time re-sync transition.

Auto-redeploy contract (2026-11-26): on `drift` the gate first triggers a Render
deploy pinned to the path-expected SHA. If the trigger succeeds the row becomes
`redeploy_triggered` and does NOT block (mismatch → redeploy, not fail). Only a
failed trigger (or api_error / no_credential / …) keeps the gate red.

# বাংলা মন্তব্য (IMPORTANT — DO NOT CHANGE WITHOUT READING):
# প্রতিটি Render সার্ভিসের live_commit অবশ্যই তার নিজস্ব `watch_paths`-এ সর্বশেষ
# পরিবর্তিত কমিটের SHA (path-expected SHA)-এর সাথে মিলতে হবে — পুরো রিপোর
# সর্বশেষ global `main` SHA-এর সাথে নয়। এতে শুধু একটি সার্ভিস (যেমন mcp) বদলালে
# বাকি সার্ভিসগুলো অযথা ব্লক বা রি-ডিপ্লয় হয় না।
"""

from __future__ import annotations

import fnmatch
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if __package__:
    from .render_trigger_deploy import (
        RenderApiError, RenderClient, deploy_commit, deploy_record,
    )
else:
    from render_trigger_deploy import (
        RenderApiError, RenderClient, deploy_commit, deploy_record,
    )

REGISTRY = Path(__file__).resolve().parents[2] / "config" / "service_registry.yaml"
LOG_DEPTH = 300  # commits scanned per service for the path-expected SHA
API_RETRIES = 2


def fail_open() -> bool:
    return os.environ.get("MESH_PARITY_FAIL_OPEN", "").strip() == "1"


def load_render_services() -> list[dict]:
    import yaml  # installed by the "Install service registry parser" step

    spec = yaml.safe_load(REGISTRY.read_text(encoding="utf-8"))
    return [
        dict(spec or {}, name=name)
        for name, spec in (spec.get("services") or {}).items()
        if isinstance(spec, dict)
        and spec.get("platform") == "render"
        and spec.get("status") != "retired"
    ]


def env_first(*names: str) -> str:
    for name in names:
        value = os.environ.get(name, "").strip()
        if value:
            return value
    return ""


def commit_files(commit: str) -> list[str]:
    out = subprocess.run(
        ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", "--first-parent", commit],
        capture_output=True, text=True, check=False,
    )
    return [line.strip() for line in out.stdout.splitlines() if line.strip()]


def path_expected_commit(watch: list[str], exclude: list[str]) -> str | None:
    """Newest commit on first-parent main that touched any watch_path (minus excludes)."""
    log = subprocess.run(
        ["git", "log", f"--max-count={LOG_DEPTH}", "--first-parent", "--format=%H"],
        capture_output=True, text=True, check=True,
    ).stdout.split()
    for commit in log:
        files = commit_files(commit)
        if files and path_hit(files, watch) and not path_hit(files, exclude):
            return commit
    return None


def path_hit(files: list[str], patterns: list[str]) -> bool:
    return any(fnmatch.fnmatchcase(f, p) for f in files for p in patterns)


def is_ancestor(older: str, newer: str) -> bool:
    out = subprocess.run(
        ["git", "merge-base", "--is-ancestor", older, newer],
        capture_output=True, text=True, check=False,
    )
    return out.returncode == 0


def latest_live(client: RenderClient, svc_id: str) -> tuple[dict | None, str]:
    last_error = ""
    for attempt in range(API_RETRIES):
        try:
            record = deploy_record(client.get_latest_deploy(svc_id))
            return record, ""
        except (RenderApiError, OSError, ValueError) as exc:  # noqa: PERF203
            last_error = f"{type(exc).__name__}: {exc}"
            if attempt + 1 < API_RETRIES:
                time.sleep(5)
    return None, last_error


def main() -> int:
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
    ).stdout.strip()

    rows: list[dict] = []
    for spec in load_render_services():
        name = spec["name"]
        svc_id = env_first(
            spec["canonical_service_id_env"], *spec.get("service_id_aliases", ())
        )
        api_key = env_first(
            spec["canonical_api_key_env"], *spec.get("api_key_aliases", [])
        )
        watch = spec.get("watch_paths") or []
        exclude = spec.get("exclude_paths") or []
        expected = path_expected_commit(watch, exclude) if watch else None

        row = {
            "service": name,
            "service_id": svc_id,
            "expected_commit": expected,
            "live_commit": None,
            "status": "skipped",
            "detail": "",
        }
        if not svc_id:
            row["detail"] = "service ID env not configured (UNREGISTERED)"
            rows.append(row)
            continue
        # বাংলা মন্তব্য: suspended CI runner কোনো প্রোডাকশন রানটাইম নয় এবং main পুশে
        # এটি কখনই অটো-ডেপ্লয় হয় না (দেখুন plan_render_deploys.py:69-72)। তাই প্যারিটি গেটে skipped।
        if name == "ci-runner":
            row["detail"] = "auxiliary runner suspended by owner (matches plan_render_deploys.py)"
            rows.append(row)
            continue
        if not api_key:
            row["status"] = "no_credential"
            row["detail"] = f"no Render API key in env ({spec['canonical_api_key_env']})"
            rows.append(row)
            continue
        if not expected:
            row["status"] = "expected_unknown"
            row["detail"] = f"no commit matching watch_paths in last {LOG_DEPTH}"
            rows.append(row)
            continue

        client = RenderClient(api_key=api_key, service_id=svc_id)
        record, error = latest_live(client, svc_id)
        if record is None:
            row["status"] = "api_error"
            row["detail"] = error
            rows.append(row)
            continue
        live_commit = deploy_commit(record)
        row["live_commit"] = live_commit
        if record.get("status") != "live":
            row["status"] = "not_live"
            row["detail"] = f"latest deploy status={record.get('status')!r}"
        elif not live_commit or not re.fullmatch(r"[0-9a-f]{40}", str(live_commit)):
            row["status"] = "no_commit_evidence"
            row["detail"] = "Render deploy record carries no usable commit"
        elif live_commit == expected or is_ancestor(expected, live_commit):
            row["status"] = "verified"
            row["detail"] = "live release is the expected commit or a descendant"
        else:
            # বাংলা মন্তব্য: drift পেলে শুধু fail না করে path-expected commit-এ
            # অটো-রিডিপ্লয় ট্রিগার করা (mismatch → redeploy, gate fail নয়)।
            # সফল হলে status=redeploy_triggered (blocking-এর বাইরে); ব্যর্থ হলেই
            # সৎ drift → blocking (fail-closed)। commit_id দেওয়া যেন branch-HEAD
            # নয়, ঠিক path-expected SHA ডিপ্লয় হয়।
            row["status"] = "drift"
            row["detail"] = f"live {live_commit[:8]} != path-expected {expected[:8]}"
            try:
                triggered = client.trigger_deploy(commit_id=expected)
                deploy_id = triggered.get("id") or triggered.get("deploy", {}).get("id") or "triggered"
                row["status"] = "redeploy_triggered"
                row["detail"] += f" (auto-redeploy pinned to {expected[:8]}: {deploy_id})"
            except Exception as trig_exc:
                row["detail"] += f" (auto-redeploy failed: {trig_exc})"
        rows.append(row)

    # redeploy_triggered = drift ছিল কিন্তু auto-redeploy সফলভাবে ট্রিগার হয়েছে —
    # সেটা blocking নয় (mismatch → redeploy, gate fail নয়)। বাকি সব অ-verified
    # অবস্থা (drift-যার retrigger ব্যর্থ, api_error, no_credential, …) blocking।
    non_blocking = ("verified", "skipped", "redeploy_triggered")
    blocking = [r for r in rows if r["status"] not in non_blocking]
    redeployed = [r for r in rows if r["status"] == "redeploy_triggered"]
    summary_lines = [
        "### Render mesh parity gate",
        "",
        "| service | status | live | path-expected | detail |",
        "|---|---|---|---|---|",
    ]
    for r in rows:
        summary_lines.append(
            "| {service} | {status} | {live} | {expected} | {detail} |".format(
                service=r["service"],
                status=r["status"],
                live=(r["live_commit"] or "—")[:8],
                expected=(r["expected_commit"] or "—")[:8],
                detail=r["detail"],
            )
        )
    summary_lines.append("")
    summary_lines.append(f"- HEAD evaluated: `{head}`")
    if redeployed:
        summary_lines.append(
            f"- **AUTO-REDEPLOY**: {len(redeployed)} service(s) were behind their "
            "path-expected commit; a deploy was triggered (pinned to the expected "
            "SHA). Re-run this gate after they go live to confirm parity."
        )
    if blocking:
        summary_lines.append(
            "- **BLOCKED**: redeploy the drifted services to the path-expected commit "
            "(`gh workflow run deploy-rollback.yml -f service=all -f target_sha=<sha>`) "
            "or re-run this workflow after they land."
        )
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY", "")
    if summary_path:
        Path(summary_path).open("a", encoding="utf-8").write("\n".join(summary_lines) + "\n")

    print(json.dumps({"head": head, "rows": rows, "blocking": len(blocking),
                      "redeploy_triggered": len(redeployed)}, indent=2))
    for r in blocking:
        print(f"::error::Mesh parity {r['status']} — {r['service']} ({r['detail']})", file=sys.stderr)
    for r in redeployed:
        print(f"::notice::Mesh parity auto-redeploy — {r['service']} ({r['detail']})", file=sys.stderr)
    if not blocking:
        if redeployed:
            print(
                f"✅ Mesh parity: {len(redeployed)} service(s) behind — auto-redeploy "
                "triggered (not blocking); remaining services verified.",
                file=sys.stderr,
            )
        else:
            print("✅ Mesh parity verified: every Render service is at its path-expected release.", file=sys.stderr)
        return 0
    if fail_open():
        print("::warning::MESH_PARITY_FAIL_OPEN=1 — reporting only, not blocking.", file=sys.stderr)
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
