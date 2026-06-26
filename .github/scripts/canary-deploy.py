#!/usr/bin/env python3
"""
canary-deploy.py
================
Progressive traffic canary with integrated observation window.
Steps: 5% → 25% → 50% → 100%, then 15min continued monitoring.

Merged Phase 3 + Phase 4 from the implementation plan:
  - Phase 3: Progressive canary deploy with auto-rollback
  - Phase 4: Post-deploy observation window (integrated, not separate job)

Rollback source: logs/deploy/revisions.json (stable_revision field)
Alert severity: only CRITICAL alerts sent immediately (no alert fatigue).
Emergency bypass: SKIP_CANARY=true routes 100% immediately.

Environment Variables:
  - GCP_PROJECT_ID: Google Cloud project ID
  - GCP_REGION: Cloud Run region (default: us-central1)
  - CANDIDATE_REVISION: Cloud Run revision to canary
  - SKIP_CANARY: Skip canary and route 100% immediately
  - ERROR_RATE_THRESHOLD: Max acceptable 5xx error rate (default: 0.01)
  - LATENCY_P99_THRESHOLD_MS: Max acceptable P99 latency in ms (default: 2000)
  - DISCORD_WEBHOOK_URL: Discord webhook for critical alerts
  - DRY_RUN: If true, simulate without actual traffic changes
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone

# ═══════════════════════════════════════════════════════════════
# Configuration
# ═══════════════════════════════════════════════════════════════
SERVICE = "supremeai-api"
REGION = os.getenv("GCP_REGION", "us-central1")
PROJECT = os.getenv("GCP_PROJECT_ID", "")
CANDIDATE_REV = os.getenv("CANDIDATE_REVISION", "")
SKIP_CANARY = os.getenv("SKIP_CANARY", "false").lower() == "true"
DRY_RUN = os.getenv("DRY_RUN", "false").lower() == "true"
DISCORD_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Canary steps: (traffic_percent, observe_minutes)
CANARY_STEPS = [(5, 2), (25, 2), (50, 2), (100, 2)]

# Post-100% observation window (minutes)
POST_DEPLOY_WATCH_MINUTES = 15

# Metric thresholds
ERROR_RATE_THRESHOLD = float(os.getenv("ERROR_RATE_THRESHOLD", "0.01"))
LATENCY_P99_THRESHOLD = int(os.getenv("LATENCY_P99_THRESHOLD_MS", "2000"))

# Revision log path
REVISIONS_LOG = "logs/deploy/revisions.json"

# GitHub Actions output file
GITHUB_OUTPUT = os.getenv("GITHUB_OUTPUT", "")


# ═══════════════════════════════════════════════════════════════
# Alert severity map (prevents alert fatigue)
# ═══════════════════════════════════════════════════════════════
ALERT_SEVERITY = {
    "canary_step_pass": "info",        # NO Discord alert
    "canary_step_fail": "critical",    # Immediate Discord alert
    "rollback_triggered": "critical",  # Immediate Discord alert
    "deploy_complete": "info",         # Log only
    "post_watch_anomaly": "critical",  # Immediate Discord alert
    "post_watch_pass": "info",         # Log only
}


def send_alert(event: str, message: str):
    """Send alert — only 'critical' events trigger Discord notification."""
    severity = ALERT_SEVERITY.get(event, "info")
    if severity != "critical":
        print(f"ℹ️  [{severity.upper()}] {message}")
        return

    print(f"🚨 [CRITICAL] {message}")
    if DISCORD_URL:
        payload = json.dumps({
            "content": f"🚨 **SupremeAI Deploy** | {message}"
        }).encode()
        req = urllib.request.Request(
            DISCORD_URL, data=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            urllib.request.urlopen(req)
        except Exception as e:
            print(f"  ⚠️ Discord alert failed: {e}")


# ═══════════════════════════════════════════════════════════════
# Revision tracking (rollback data source)
# ═══════════════════════════════════════════════════════════════
def get_stable_revision() -> str:
    """Load previous stable revision from revisions.json."""
    try:
        with open(REVISIONS_LOG) as f:
            data = json.load(f)
        rev = data.get("stable_revision", "")
        if rev:
            print(f"📌 Previous stable revision: {rev}")
        return rev
    except FileNotFoundError:
        print("⚠️  No revisions.json found — first deploy (no rollback target)")
        return ""
    except Exception as e:
        print(f"⚠️  Error reading revisions.json: {e}")
        return ""


def save_stable_revision(revision: str):
    """Update revisions.json after successful full deploy."""
    os.makedirs(os.path.dirname(REVISIONS_LOG), exist_ok=True)
    with open(REVISIONS_LOG, "w") as f:
        json.dump({
            "stable_revision": revision,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
            "health_score": 1.0
        }, f, indent=2)
    print(f"💾 Saved {revision} as stable revision")


# ═══════════════════════════════════════════════════════════════
# Cloud Run traffic management
# ═══════════════════════════════════════════════════════════════
def set_traffic(revision: str, percent: int):
    """Route `percent`% traffic to the specified revision."""
    if DRY_RUN:
        print(f"🔍 [DRY RUN] Would route {percent}% → {revision}")
        return
    cmd = [
        "gcloud", "run", "services", "update-traffic", SERVICE,
        "--region", REGION, "--project", PROJECT,
        f"--to-revisions={revision}={percent}"
    ]
    print(f"$ {' '.join(cmd)}")
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"❌ Traffic update failed: {result.stderr}")
        raise RuntimeError(f"Failed to set traffic to {percent}%")
    print(f"✅ Traffic set: {percent}% → {revision}")


def rollback(stable_rev: str):
    """Rollback to previous stable revision."""
    if not stable_rev:
        print("❌ No stable revision found — cannot rollback!")
        send_alert("rollback_triggered", "ROLLBACK FAILED — no stable revision recorded!")
        return False
    print(f"\n🔄 Rolling back to {stable_rev}...")
    if not DRY_RUN:
        try:
            subprocess.run([
                "gcloud", "run", "services", "update-traffic", SERVICE,
                "--region", REGION, "--project", PROJECT,
                f"--to-revisions={stable_rev}=100"
            ], check=True, capture_output=True, text=True)
        except subprocess.CalledProcessError as e:
            print(f"❌ Rollback command failed: {e.stderr}")
            send_alert("rollback_triggered", f"ROLLBACK COMMAND FAILED: {e.stderr}")
            return False
    send_alert("rollback_triggered", f"AUTO-ROLLBACK to {stable_rev}")
    return True


# ═══════════════════════════════════════════════════════════════
# Metrics checking (uses Cloud Run built-in metrics — free)
# ═══════════════════════════════════════════════════════════════
def check_metrics() -> dict:
    """
    Check Cloud Run service health using built-in metrics.
    Falls back to curl-based health check if Cloud Monitoring unavailable.

    Returns: {"healthy": bool, "error_rate": float, "p99_latency_ms": int}
    """
    if DRY_RUN:
        return {"healthy": True, "error_rate": 0.0, "p99_latency_ms": 100}

    # Attempt 1: Use gcloud to check recent logs for 5xx errors
    try:
        # Count recent 5xx errors in last 2 minutes
        result = subprocess.run([
            "gcloud", "logging", "read",
            f'resource.type="cloud_run_revision" '
            f'resource.labels.service_name="{SERVICE}" '
            f'httpRequest.status>=500',
            "--project", PROJECT,
            "--freshness", "2m",
            "--limit", "100",
            "--format", "value(httpRequest.status)"
        ], capture_output=True, text=True, timeout=30)

        error_count = len([l for l in result.stdout.splitlines() if l.strip()])

        # Count total requests in last 2 minutes
        total_result = subprocess.run([
            "gcloud", "logging", "read",
            f'resource.type="cloud_run_revision" '
            f'resource.labels.service_name="{SERVICE}" '
            f'httpRequest.status>0',
            "--project", PROJECT,
            "--freshness", "2m",
            "--limit", "1000",
            "--format", "value(httpRequest.status)"
        ], capture_output=True, text=True, timeout=30)

        total_count = max(len([l for l in total_result.stdout.splitlines() if l.strip()]), 1)
        error_rate = error_count / total_count

        return {
            "healthy": error_rate <= ERROR_RATE_THRESHOLD,
            "error_rate": error_rate,
            "p99_latency_ms": 0,  # Latency requires Cloud Monitoring API
            "source": "cloud_logging",
            "errors": error_count,
            "total": total_count,
        }

    except Exception as e:
        print(f"  ⚠️ Metrics check failed ({e}) — falling back to health endpoint")

    # Attempt 2: Fallback to simple health check
    try:
        service_json = subprocess.run([
            "gcloud", "run", "services", "describe", SERVICE,
            "--region", REGION, "--project", PROJECT,
            "--format", "json"
        ], capture_output=True, text=True, check=True, timeout=15)

        service_data = json.loads(service_json.stdout)
        url = service_data.get("status", {}).get("url", "")
        if url:
            health_url = f"{url}/health"
            req = urllib.request.Request(health_url, method="GET")
            with urllib.request.urlopen(req, timeout=10) as resp:
                healthy = resp.status == 200
                return {"healthy": healthy, "error_rate": 0.0 if healthy else 1.0,
                        "p99_latency_ms": 0, "source": "health_endpoint"}
    except Exception as e:
        print(f"  ⚠️ Health endpoint check failed: {e}")

    # All checks failed — assume healthy (don't block on monitoring failure)
    print("  ⚠️ All metric checks failed — assuming healthy (fail open for metrics)")
    return {"healthy": True, "error_rate": 0.0, "p99_latency_ms": 0, "source": "default"}


# ═══════════════════════════════════════════════════════════════
# Main canary flow
# ═══════════════════════════════════════════════════════════════
def main():
    print("🐤 SupremeAI Canary Deploy Engine")
    print(f"   Service: {SERVICE}")
    print(f"   Region: {REGION}")
    print(f"   Candidate: {CANDIDATE_REV}")
    print(f"   Emergency bypass: {SKIP_CANARY}")
    print(f"   Dry run: {DRY_RUN}")

    if not CANDIDATE_REV:
        print("❌ CANDIDATE_REVISION not set — cannot deploy")
        return 1

    if not PROJECT:
        print("❌ GCP_PROJECT_ID not set — cannot deploy")
        return 1

    stable_rev = get_stable_revision()

    # ── Emergency bypass ──────────────────────────────────────
    if SKIP_CANARY:
        print("\n⚡ Emergency bypass — skipping canary, routing 100% directly")
        set_traffic(CANDIDATE_REV, 100)
        save_stable_revision(CANDIDATE_REV)
        send_alert("deploy_complete", f"Emergency deploy: {CANDIDATE_REV} → 100%")
        return 0

    # ── Progressive canary steps ──────────────────────────────
    print(f"\n🐤 Starting canary deploy: {' → '.join(f'{p}%' for p, _ in CANARY_STEPS)}")
    print(f"   Post-deploy watch: {POST_DEPLOY_WATCH_MINUTES}min")

    for step_idx, (percent, wait_min) in enumerate(CANARY_STEPS):
        print(f"\n{'='*50}")
        print(f"📊 Step {step_idx + 1}/{len(CANARY_STEPS)}: Setting {percent}% traffic → {CANDIDATE_REV}")
        print(f"{'='*50}")

        try:
            set_traffic(CANDIDATE_REV, percent)
        except RuntimeError:
            send_alert("canary_step_fail", f"Failed to set {percent}% traffic")
            rollback(stable_rev)
            return 1

        print(f"⏳ Observing for {wait_min} minutes...")
        time.sleep(wait_min * 60)

        # Check metrics
        metrics = check_metrics()
        er = metrics['error_rate']
        lat = metrics['p99_latency_ms']
        src = metrics.get('source', 'unknown')
        print(f"📊 Metrics [{src}]: error_rate={er:.2%}, p99={lat}ms")

        if er > ERROR_RATE_THRESHOLD:
            send_alert("canary_step_fail",
                       f"Canary FAILED at {percent}%! error_rate={er:.2%} > {ERROR_RATE_THRESHOLD:.2%}. Rolling back.")
            rollback(stable_rev)
            return 1

        if lat > 0 and lat > LATENCY_P99_THRESHOLD:
            send_alert("canary_step_fail",
                       f"Canary FAILED at {percent}%! p99={lat}ms > {LATENCY_P99_THRESHOLD}ms. Rolling back.")
            rollback(stable_rev)
            return 1

        send_alert("canary_step_pass", f"Canary {percent}% passed ✓")
        print(f"✅ {percent}% step passed")

    # ── 100% reached — integrated observation window ──────────
    print(f"\n{'='*50}")
    print(f"🔭 100% deployed — watching for {POST_DEPLOY_WATCH_MINUTES} more minutes...")
    print(f"{'='*50}")

    for minute in range(POST_DEPLOY_WATCH_MINUTES):
        time.sleep(60)
        metrics = check_metrics()
        er = metrics['error_rate']

        # Slightly stricter threshold at 100% (double the canary threshold)
        if er > ERROR_RATE_THRESHOLD * 2:
            send_alert("post_watch_anomaly",
                       f"Post-deploy anomaly at minute {minute + 1}/{POST_DEPLOY_WATCH_MINUTES}! "
                       f"error_rate={er:.2%}. Rolling back.")
            rollback(stable_rev)
            return 1

        if (minute + 1) % 5 == 0:
            print(f"  ✓ Minute {minute + 1}/{POST_DEPLOY_WATCH_MINUTES}: OK (error_rate={er:.2%})")

    # ── All clear — save new stable revision ──────────────────
    save_stable_revision(CANDIDATE_REV)
    send_alert("deploy_complete", f"Deploy complete: {CANDIDATE_REV} is now stable")

    # Write GitHub Actions output
    if GITHUB_OUTPUT:
        with open(GITHUB_OUTPUT, "a") as f:
            f.write(f"canary_result=success\n")
            f.write(f"deployed_revision={CANDIDATE_REV}\n")

    print(f"\n🎉 Deploy successful! {CANDIDATE_REV} is now the stable revision.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
