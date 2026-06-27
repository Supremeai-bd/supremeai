#!/usr/bin/env python3
# ═══════════════════════════════════════════════════════════════════════════════
# ⚖️ SupremeAI CI Decision Engine — Phase 5
# ═══════════════════════════════════════════════════════════════════════════════
# এই স্ক্রিপ্ট Evaluator result অনুযায়ী সিদ্ধান্ত নেয়:
#   • confidence >= 0.95 + risk == "safe" → MERGE + DEPLOY
#   • confidence >= 0.7 + risk == "caution" → RETRY (no merge)
#   • confidence < 0.7 OR risk == "dangerous" → DISCARD + ALERT
#   • Human alert: GitHub issue, Slack, Discord
# ═══════════════════════════════════════════════════════════════════════════════

import json
import os
import sys
import urllib.request
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# কনফিগারেশন
# ═══════════════════════════════════════════════════════════════
FINAL_CONFIDENCE = float(os.environ.get("FINAL_CONFIDENCE", "0.0"))
RISK_ASSESSMENT = os.environ.get("RISK_ASSESSMENT", "dangerous")
DEPLOY_RECOMMENDED = os.environ.get("DEPLOY_RECOMMENDED", "false").lower() == "true"
HUMAN_REVIEW = os.environ.get("HUMAN_REVIEW", "true").lower() == "true"
REASONING = os.environ.get("REASONING", "")

FAILED_JOBS = os.environ.get("FAILED_JOBS", "[]")
FIX_BRANCHES = os.environ.get("FIX_BRANCHES", "")

GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
BRANCH = os.environ.get("BRANCH", "main")
RUN_ID = os.environ.get("RUN_ID", "0")
REPO = os.environ.get("REPO", "")

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK_URL", "")
DISCORD_WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "")

# Thresholds
DEPLOY_THRESHOLD = 0.95
RETRY_THRESHOLD = 0.70


def set_output(name: str, value: str):
    """GitHub Actions output সেট করে"""
    if "GITHUB_OUTPUT" in os.environ:
        with open(os.environ["GITHUB_OUTPUT"], "a") as fh:
            fh.write(f"{name}={value}\n")
    print(f"OUTPUT: {name}={value}")


def merge_fix_branches(fix_branches: str) -> bool:
    """Fix branch গুলো main এ merge করে"""
    if not fix_branches:
        return True

    import subprocess

    branches = [b.strip() for b in fix_branches.split(",") if b.strip()]
    if not branches:
        return True

    print(f"🔀 Fix branches merge করা হচ্ছে: {branches}")

    try:
        # Main branch checkout
        subprocess.run(["git", "fetch", "origin", BRANCH], check=True, capture_output=True)
        subprocess.run(["git", "checkout", BRANCH], check=True, capture_output=True)

        for fb in branches:
            print(f"  → Merging {fb} into {BRANCH}")
            result = subprocess.run(
                ["git", "merge", "--no-ff", f"origin/{fb}", "-m", f"ci(auto-fix): merge {fb} [run {RUN_ID}]"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode != 0:
                print(f"  ⚠️ Merge conflict in {fb} — aborting")
                subprocess.run(["git", "merge", "--abort"], check=False, capture_output=True)
                return False

        # Push merged main
        push_result = subprocess.run(
            ["git", "push", "origin", BRANCH],
            capture_output=True,
            text=True,
            check=False
        )
        if push_result.returncode == 0:
            print(f"✅ Fix branches merged successfully")
            return True
        else:
            print(f"❌ Push failed: {push_result.stderr}")
            return False

    except Exception as e:
        print(f"❌ Merge error: {e}")
        return False


def delete_fix_branches(fix_branches: str):
    """Fix branch গুলো ডিলিট করে"""
    if not fix_branches:
        return

    import subprocess

    branches = [b.strip() for b in fix_branches.split(",") if b.strip()]
    for fb in branches:
        print(f"🗑️ Deleting fix branch: {fb}")
        subprocess.run(["git", "push", "origin", "--delete", fb], check=False, capture_output=True)


def create_github_issue(title: str, body: str, labels: list) -> Optional[int]:
    """GitHub issue তৈরি করে"""
    if not GITHUB_TOKEN or not REPO:
        return None

    try:
        payload = {
            "title": title,
            "body": body,
            "labels": labels
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f"https://api.github.com/repos/{REPO}/issues",
            data=data,
            headers={
                "Authorization": f"Bearer {GITHUB_TOKEN}",
                "Accept": "application/vnd.github+json",
                "Content-Type": "application/json"
            },
            method="POST"
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            issue_number = result.get("number")
            print(f"✅ GitHub issue created: #{issue_number}")
            return issue_number

    except Exception as e:
        print(f"⚠️ GitHub issue creation failed: {e}")
        return None


def send_slack_alert(message: str):
    """Slack এ alert পাঠায়"""
    if not SLACK_WEBHOOK:
        return

    try:
        payload = {"text": message}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            SLACK_WEBHOOK,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        print("✅ Slack alert sent")
    except Exception as e:
        print(f"⚠️ Slack alert failed: {e}")


def send_discord_alert(message: str):
    """Discord এ alert পাঠায়"""
    if not DISCORD_WEBHOOK:
        return

    try:
        payload = {"content": message}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            DISCORD_WEBHOOK,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        urllib.request.urlopen(req, timeout=10)
        print("✅ Discord alert sent")
    except Exception as e:
        print(f"⚠️ Discord alert failed: {e}")


def dispatch_retry_run(failed_jobs: list) -> bool:
    """নতুন retry run dispatch করে"""
    if not GITHUB_TOKEN or not REPO:
        return False

    try:
        # জব নামকে forced_jobs ফরম্যাটে কনভার্ট
        job_mapping = {
            "🐍 ব্যাকএন্ড টেস্ট": "backend-test",
            "🎨 স্টুডিও ক্লায়েন্ট বিল্ড": "studio-build",
            "📱 মোবাইল অ্যাপ অ্যানালাইসিস": "mobile-analyze",
            "💬 ওয়েব চ্যাট বিল্ড": "webchat-build",
            "🧩 VS Code এক্সটেনশন বিল্ড": "vscode-build",
            "🤖 LLM প্রম্পট ইভ্যালুয়েশন": "prompt-eval"
        }

        forced = []
        for job in failed_jobs:
            if job in job_mapping:
                forced.append(job_mapping[job])

        payload = {
            'ref': BRANCH,
            'inputs': {
                'forced_jobs': json.dumps(forced),
                'is_retry': 'true',
                'ai_api_provider': 'supremeai'
            }
        }

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            f'https://api.github.com/repos/{REPO}/actions/workflows/supreme-ci-v3.yml/dispatches',
            data=data,
            headers={
                'Authorization': f'Bearer {GITHUB_TOKEN}',
                'Accept': 'application/vnd.github+json',
                'Content-Type': 'application/json'
            },
            method='POST'
        )

        with urllib.request.urlopen(req, timeout=30) as resp:
            print(f'✅ Retry dispatched! Status: {resp.status}')
            return True

    except Exception as e:
        print(f'❌ Retry dispatch failed: {e}')
        return False


def main():
    print("=" * 60)
    print("⚖️ SupremeAI CI Decision Engine — Phase 5")
    print("=" * 60)

    print(f"📊 Input:")
    print(f"  Confidence: {FINAL_CONFIDENCE:.2f}")
    print(f"  Risk: {RISK_ASSESSMENT}")
    print(f"  Deploy Recommended: {DEPLOY_RECOMMENDED}")
    print(f"  Human Review: {HUMAN_REVIEW}")
    print(f"  Fix Branches: {FIX_BRANCHES}")

    # সিদ্ধান্ত নিন
    decision = "discard"

    if FINAL_CONFIDENCE >= DEPLOY_THRESHOLD and RISK_ASSESSMENT == "safe" and DEPLOY_RECOMMENDED:
        decision = "deploy"
        print(f"\n🟢 DECISION: DEPLOY — confidence {FINAL_CONFIDENCE:.2f} >= {DEPLOY_THRESHOLD}, risk=safe")

        # Fix branches merge করুন
        if FIX_BRANCHES:
            merged = merge_fix_branches(FIX_BRANCHES)
            if not merged:
                print("⚠️ Merge failed — falling back to retry")
                decision = "retry"

    elif FINAL_CONFIDENCE >= RETRY_THRESHOLD and RISK_ASSESSMENT in ("safe", "caution"):
        decision = "retry"
        print(f"\n🟡 DECISION: RETRY — confidence {FINAL_CONFIDENCE:.2f} >= {RETRY_THRESHOLD}, risk={RISK_ASSESSMENT}")

        # Fix branches delete করুন (retry এ merge নয়)
        delete_fix_branches(FIX_BRANCHES)

        # Retry dispatch
        try:
            failed_jobs_list = json.loads(FAILED_JOBS) if FAILED_JOBS else []
        except:
            failed_jobs_list = []

        if failed_jobs_list:
            dispatched = dispatch_retry_run(failed_jobs_list)
            if dispatched:
                print("✅ Retry run dispatched")
            else:
                print("❌ Retry dispatch failed")

        # Human review issue তৈরি
        if HUMAN_REVIEW:
            issue_body = f"""## 🟡 CI Auto-Fix Requires Human Review

**Run ID:** {RUN_ID}
**Branch:** {BRANCH}
**Confidence:** {FINAL_CONFIDENCE:.2f}
**Risk:** {RISK_ASSESSMENT}

**Reasoning:**
{REASONING}

**Failed Jobs:**
{FAILED_JOBS}

**Fix Branches:**
{FIX_BRANCHES}

A retry has been dispatched. Please review the fixes before merging.
"""
            create_github_issue(
                f"🟡 CI Review Required: Auto-fix retry [run {RUN_ID}]",
                issue_body,
                ["ci", "auto-fix", "review-required"]
            )

    else:
        decision = "discard"
        print(f"\n🔴 DECISION: DISCARD — confidence {FINAL_CONFIDENCE:.2f} < {RETRY_THRESHOLD} OR risk={RISK_ASSESSMENT}")

        # Fix branches delete
        delete_fix_branches(FIX_BRANCHES)

        # Critical alert
        alert_message = f"""🚨 **SupremeAI CI CRITICAL ALERT**

Run: {RUN_ID}
Branch: {BRANCH}
Confidence: {FINAL_CONFIDENCE:.2f}
Risk: {RISK_ASSESSMENT}

Auto-fix was DISCARDED. All fix branches deleted.

Reasoning: {REASONING}

Failed Jobs: {FAILED_JOBS}
"""

        # GitHub critical issue
        issue_body = f"""## 🔴 CI Auto-Fix DISCARDED — Critical Alert

**Run ID:** {RUN_ID}
**Branch:** {BRANCH}
**Confidence:** {FINAL_CONFIDENCE:.2f}
**Risk:** {RISK_ASSESSMENT}

**Reasoning:**
{REASONING}

**Failed Jobs:**
{FAILED_JOBS}

**Action Taken:**
- All fix branches deleted
- Pipeline stopped
- Manual intervention required

**Next Steps:**
1. Review the failed jobs manually
2. Fix the issues in a new branch
3. Push the fixes and re-run CI
"""
        create_github_issue(
            f"🔴 CI CRITICAL: Auto-fix discarded [run {RUN_ID}]",
            issue_body,
            ["ci", "auto-fix", "critical", "help wanted"]
        )

        # Slack/Discord alert
        send_slack_alert(alert_message)
        send_discord_alert(alert_message)

    print("\n" + "=" * 60)
    print(f"📋 Final Decision: {decision.upper()}")
    print("=" * 60)

    set_output("decision", decision)
    set_output("retry_dispatched", "true" if decision == "retry" else "false")

    return 0


if __name__ == "__main__":
    sys.exit(main())
