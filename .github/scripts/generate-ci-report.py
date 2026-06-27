#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

def get_all_jobs_from_yaml(filepath):
    jobs = {}
    current_job_id = None
    in_jobs = False
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        for line in lines:
            stripped = line.strip()
            if line.startswith('jobs:'):
                in_jobs = True
                continue
            if in_jobs:
                if line and not line.startswith(' ') and not line.startswith('\t') and not stripped.startswith('#'):
                    if stripped:
                        in_jobs = False
                        continue
                if line.startswith('  ') and not line.startswith('   ') and ':' in line and not stripped.startswith('#') and not stripped.startswith('-'):
                    parts = line.split(':')
                    current_job_id = parts[0].strip()
                    jobs[current_job_id] = {'id': current_job_id, 'name': current_job_id}
                if current_job_id and stripped.startswith('name:'):
                    name_str = stripped.split('name:')[1].strip().strip('\'\"')
                    jobs[current_job_id]['name'] = name_str
    except Exception as e:
        print(f"⚠️ Error parsing YAML: {e}")
    return list(jobs.values())

def main():
    run_id = os.environ.get("GITHUB_RUN_ID")
    repository = os.environ.get("GITHUB_REPOSITORY")
    token = os.environ.get("GITHUB_TOKEN")
    server_url = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    ref_name = os.environ.get("GITHUB_REF_NAME")
    actor = os.environ.get("GITHUB_ACTOR")
    sha = os.environ.get("GITHUB_SHA", "")
    short_sha = sha[:7] if sha else "unknown"

    if not run_id or not repository or not token:
        print("❌ Missing required environment variables (GITHUB_RUN_ID, GITHUB_REPOSITORY, GITHUB_TOKEN)")
        return 1

    # Fetch jobs from GitHub API
    url = f"https://api.github.com/repos/{repository}/actions/runs/{run_id}/jobs?per_page=100"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json"
        }
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            jobs = data.get("jobs", [])
    except Exception as e:
        print(f"❌ Failed to fetch jobs from GitHub API: {e}")
        return 1

    # Parse all jobs from the workflow YAML file statically
    yaml_jobs = get_all_jobs_from_yaml(".github/workflows/supreme-ci.yml")
    
    passed_jobs = []
    failed_jobs = []
    skipped_jobs = []
    
    # Filter out the current job from active list to avoid treating it as running/skipped
    active_api_jobs = [j for j in jobs if j.get("name") != "📊 CI রিপোর্ট ও ড্যাশবোর্ড লগ"]

    for j in active_api_jobs:
        name = j.get("name", "Unknown Job")
        conclusion = j.get("conclusion")
        
        if conclusion == "success":
            passed_jobs.append(j)
        elif conclusion in ("failure", "timed_out"):
            failed_jobs.append(j)
        else:
            skipped_jobs.append(j)

    # Identify pending/downstream jobs (present in YAML but not yet in API response)
    api_job_names = {j["name"] for j in jobs}
    pending_jobs = []
    for yj in yaml_jobs:
        if yj["name"] == "📊 CI রিপোর্ট ও ড্যাশবোর্ড লগ":
            continue
        matched = False
        for aj_name in api_job_names:
            if yj["name"] == aj_name or yj["name"] in aj_name:
                matched = True
                break
        if not matched:
            pending_jobs.append(yj)

    passed_count = len(passed_jobs)
    failed_count = len(failed_jobs)
    skipped_count = len(skipped_jobs)
    pending_count = len(pending_jobs)
    total_count = passed_count + failed_count + skipped_count + pending_count

    # Determine overall status
    if failed_count > 0:
        overall_emoji = "🔴"
        overall_text = "FAILED"
    else:
        overall_emoji = "🟢"
        overall_text = "ALL PASSED"

    run_url = f"{server_url}/{repository}/actions/runs/{run_id}"

    # Build GITHUB_STEP_SUMMARY Markdown
    summary_lines = []
    summary_lines.append(f"# {overall_emoji} SupremeAI CI Report")
    summary_lines.append("")
    summary_lines.append(f"**Branch:** `{ref_name}` | **Commit:** `{short_sha}` | **Actor:** `{actor}`")
    summary_lines.append("")
    summary_lines.append(f"## 📊 Summary: {overall_emoji} {overall_text} (Total Jobs: {total_count})")
    summary_lines.append("| Status | Count |")
    summary_lines.append("|--------|-------|")
    summary_lines.append(f"| ✅ Passed | {passed_count} |")
    summary_lines.append(f"| ❌ Failed | {failed_count} |")
    summary_lines.append(f"| ⏭️ Skipped | {skipped_count} |")
    summary_lines.append(f"| ⏳ Pending / Downstream | {pending_count} |")
    summary_lines.append("")

    if failed_count > 0:
        summary_lines.append("### 🔴 Failed Jobs (Action Required!)")
        summary_lines.append("| Status | Job | Result |")
        summary_lines.append("|--------|-----|--------|")
        for j in failed_jobs:
            summary_lines.append(f"| ❌ | **{j['name']}** | `{j['conclusion']}` |")
        summary_lines.append("")
        summary_lines.append("> [!CAUTION]")
        summary_lines.append(f"> **{failed_count} job(s) failed!** Please inspect the logs.")
        summary_lines.append("")

    if passed_count > 0:
        summary_lines.append(f"### ✅ Passed Jobs ({passed_count})")
        summary_lines.append("| Status | Job | Result |")
        summary_lines.append("|--------|-----|--------|")
        for j in passed_jobs:
            summary_lines.append(f"| ✅ | {j['name']} | `{j['conclusion']}` |")
        summary_lines.append("")

    if skipped_count > 0:
        summary_lines.append(f"### ⏭️ Skipped/Cancelled Jobs ({skipped_count})")
        summary_lines.append("| Status | Job | Result |")
        summary_lines.append("|--------|-----|--------|")
        for j in skipped_jobs:
            res = j.get("conclusion") or "skipped"
            summary_lines.append(f"| ⏭️ | {j['name']} | `{res}` |")
        summary_lines.append("")

    if pending_count > 0:
        summary_lines.append(f"### ⏳ Pending / Downstream Jobs ({pending_count})")
        summary_lines.append("| Status | Job | Result |")
        summary_lines.append("|--------|-----|--------|")
        for pj in pending_jobs:
            summary_lines.append(f"| ⏳ | {pj['name']} | `pending` |")
        summary_lines.append("")

    summary_lines.append("---")
    summary_lines.append(f"🔗 [Full Run Log]({run_url})")

    summary_text = "\n".join(summary_lines)

    # Write to GITHUB_STEP_SUMMARY
    step_summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if step_summary_path:
        with open(step_summary_path, "a", encoding="utf-8") as fh:
            fh.write(summary_text)
    
    # Write to local file for artifact upload
    with open("failure-report.md", "w", encoding="utf-8") as fh:
        fh.write(summary_text)

    # Create logs/ci directory
    os.makedirs("logs/ci", exist_ok=True)

    # Write to logs/ci/latest.md and run specific md
    with open("logs/ci/latest.md", "w", encoding="utf-8") as fh:
        fh.write(summary_text)
    with open(f"logs/ci/run-{run_id}.md", "w", encoding="utf-8") as fh:
        fh.write(summary_text)

    # Build JSON log
    timestamp = datetime.now(timezone.utc).isoformat()
    json_log = {
        "run_id": run_id,
        "timestamp": timestamp,
        "branch": ref_name,
        "commit": short_sha,
        "actor": actor,
        "run_url": run_url,
        "overall": overall_text,
        "overall_emoji": overall_emoji,
        "passed": passed_count,
        "failed": failed_count,
        "skipped": skipped_count,
        "pending": pending_count,
        "total": total_count,
        "jobs": {j["name"]: {"status": j.get("status"), "conclusion": j.get("conclusion")} for j in jobs}
    }

    # Write JSON logs
    with open("logs/ci/latest.json", "w", encoding="utf-8") as fh:
        json.dump(json_log, fh, indent=2, ensure_ascii=False)
    with open(f"logs/ci/run-{run_id}.json", "w", encoding="utf-8") as fh:
        json.dump(json_log, fh, indent=2, ensure_ascii=False)

    # Determine all_critical_passed
    critical_job = next((j for j in jobs if "ব্যাকএন্ড টেস্ট" in j.get("name", "") or "backend-test" in j.get("name", "")), None)
    if critical_job and critical_job.get("conclusion") not in ("success", "skipped", None):
        all_critical_passed = "false"
    else:
        all_critical_passed = "true"

    # Default overall_confidence to 1.00
    overall_confidence = "1.00"

    # Write outputs for GitHub Actions step
    github_output_path = os.environ.get("GITHUB_OUTPUT")
    if github_output_path:
        with open(github_output_path, "a", encoding="utf-8") as fh:
            fh.write(f"failed_count={failed_count}\n")
            fh.write(f"passed_count={passed_count}\n")
            fh.write(f"skipped_count={skipped_count}\n")
            fh.write(f"pending_count={pending_count}\n")
            fh.write(f"total_count={total_count}\n")
            fh.write(f"overall_text={overall_text}\n")
            fh.write(f"overall_emoji={overall_emoji}\n")
            fh.write(f"all_critical_passed={all_critical_passed}\n")
            fh.write(f"overall_confidence={overall_confidence}\n")
            
            # If any fix was applied (detect based on jobs conclusions)
            any_fix = "true" if any("fix_applied" in str(j.get("steps", [])) for j in jobs) else "false"
            fh.write(f"any_fix_applied={any_fix}\n")

            failed_names = [j['name'] for j in failed_jobs]
            fh.write(f"failed_jobs={json.dumps(failed_names)}\n")

    print("✅ CI Report generated successfully.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
