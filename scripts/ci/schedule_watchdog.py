#!/usr/bin/env python3
"""Schedule Watchdog — visibility-flip cron self-heal (#58, Plan-B of #52).

বাংলা সারসংক্ষেপ:
------------------
2026-10-09 public→private flip-এর পর GitHub পুরো repo-র scheduled workflows বন্ধ করে
দেয় (repo-wide শেষ schedule event = 11:02:49Z)। disable→enable API toggle যথেষ্ট
নয় (16:43 + 17:13 স্লট silent)। এই watchdog schedule-independent — বেঁচে থাকা
ইভেন্টে (push / issues / dispatch) চলে এবং প্রতিটি cron-যুক্ত workflow-এর জন্য:

  ১. workflow YAML থেকে cron পড়ে পরবর্তী প্রত্যাশিত ফায়ার হিসাব করে (UTC);
  ২. last schedule run তার ৩০min grace-এর চেয়ে বাসি হলে → disable→enable re-arm;
  ৩. শেষ যেকোনো-ইভেন্ট রানও বাসি হলে → workflow_dispatch compensation
     (concurrency + নিজের গার্ড ওভারল্যাপ সামলায়);
  ৪. `workflow_dispatch` অক্ষম workflow-তে re-arm-ই যথেষ্ট; নিজেকে কখনো ধরে না
     (loop-guard) — `schedule-watchdog.yml` সবসময় skip।

Zero-dependency (urllib + PyYAML only)। GH_TOKEN + GH_REPO env প্রত্যাশিত।
Usage:
  python scripts/ci/schedule_watchdog.py            # re-arm + compensate (CI)
  python scripts/ci/schedule_watchdog.py --dry-run  # report only, no writes
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GRACE_MIN = 30          # cron মিসড ঘোষণার অতিরিক্ত সহনশীলতা
SELF_PATH_SUFFIX = "schedule-watchdog.yml"
API = "https://api.github.com"


# ────────────────────────────── cron math ──────────────────────────────
def _field(expr: str, lo: int, hi: int) -> set[int]:
    vals: set[int] = set()
    for part in expr.split(","):
        part = part.strip()
        if part == "*":
            vals.update(range(lo, hi + 1))
        elif part.startswith("*/"):
            step = int(part[2:])
            vals.update(range(lo, hi + 1, step))
        elif "-" in part:
            a, b = part.split("-", 1)
            vals.update(range(int(a), int(b) + 1))
        else:
            vals.add(int(part))
    return vals


def cron_next(expr: str, after: dt.datetime) -> dt.datetime:
    """5-field cron (UTC) — `after`-এর পরের প্রথম ফায়ার টাইম (স্ট্যান্ডার্ড dom/dow OR রুল)।"""
    mi, h, dom, mon, dow = expr.split()
    mins = _field(mi, 0, 59)
    hrs = _field(h, 0, 23)
    doms = _field(dom, 1, 31)
    mons = _field(mon, 1, 12)
    dows = _field(dow, 0, 6)
    if "7" in dow.replace("-", ",").split(","):
        dows.add(0)  # 7 == Sunday

    dom_restricted = dom != "*"
    dow_restricted = dow != "*"

    def cron_dow(t: dt.datetime) -> int:
        return (t.weekday() + 1) % 7  # Python Monday=0 → cron 0=Sunday

    t = (after + dt.timedelta(minutes=1)).replace(second=0, microsecond=0)
    limit = after + dt.timedelta(days=500)
    while t <= limit:
        if t.month not in mons:
            nxt = (t.replace(day=1) + dt.timedelta(days=32)).replace(day=1, hour=0, minute=0)
            t = nxt
            continue
        if dom_restricted and dow_restricted:
            day_ok = (t.day in doms) or (cron_dow(t) in dows)
        else:
            day_ok = (t.day in doms if dom_restricted else True) and (
                cron_dow(t) in dows if dow_restricted else True
            )
        if day_ok:
            for hh in sorted(hrs):
                for mm in sorted(mins):
                    cand = t.replace(hour=hh, minute=mm)
                    if cand > after:
                        return cand
        t = (t + dt.timedelta(days=1)).replace(hour=0, minute=0)
    raise ValueError(f"cron_next: no fire within 500d for {expr!r}")


# ────────────────────────────── GitHub API ──────────────────────────────
def api(method: str, path: str, token: str, body: dict | None = None) -> tuple[int, dict | list]:
    req = urllib.request.Request(
        f"{API}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github+json",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.load(resp) if resp.status != 204 else {}
            return resp.status, payload
    except urllib.error.HTTPError as exc:
        return exc.code, {}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="report only — কোনো লেখা নয়")
    args = ap.parse_args()

    token = os.environ.get("GH_TOKEN", "").strip()
    repo = os.environ.get("GH_REPO", "").strip()
    if not token or "/" not in repo:
        print("WATCHDOG: GH_TOKEN/GH_REPO missing — fail-closed (non-zero)", file=sys.stderr)
        return 2

    _owner, _name = repo.split("/", 1)
    code, repo_info = api("GET", f"/repos/{repo}", token)
    if code != 200:
        print(f"WATCHDOG: repo lookup failed ({code})", file=sys.stderr)
        return 2
    default_branch = repo_info["default_branch"]

    code, tree = api("GET", f"/repos/{repo}/contents/.github/workflows", token)
    if code != 200:
        print(f"WATCHDOG: workflows listing failed ({code})", file=sys.stderr)
        return 2

    import yaml  # runner: pip install pyyaml (workflow step)

    code, wfs = api("GET", f"/repos/{repo}/actions/workflows?per_page=100", token)
    if code != 200:
        print(f"WATCHDOG: workflows api failed ({code})", file=sys.stderr)
        return 2
    wf_by_path = {w["path"]: w for w in wfs.get("workflows", [])}

    now = dt.datetime.now(dt.timezone.utc)
    report: list[str] = []
    re_armed = compensated = 0
    evidence_missing = False

    for item in tree:
        path = item["path"]
        if not path.endswith((".yml", ".yaml")):
            continue
        if path.endswith(SELF_PATH_SUFFIX):
            report.append(f"SKIP(self-loop-guard) | {path}")
            continue
        code, raw = api("GET", f"/repos/{repo}/contents/{path}", token)
        if code != 200:
            report.append(f"WARN(read {code}) | {path}")
            continue
        try:
            spec = yaml.safe_load(__import__("base64").b64decode(raw["content"]).decode())
        except Exception as exc:
            report.append(f"WARN(yaml {exc.__class__.__name__}) | {path}")
            continue
        trig = spec.get("on") if isinstance(spec, dict) else None
        trig = trig if isinstance(trig, dict) else (spec.get(True) if isinstance(spec, dict) else None)
        schedules = (trig or {}).get("schedule") or []
        crons = [s.get("cron", "") for s in schedules if isinstance(s, dict) and s.get("cron")]
        if not crons:
            continue

        wf = wf_by_path.get(path)
        if not wf:
            report.append(f"WARN(no-wf-id) | {path}")
            continue

        # শেষ schedule-run
        code, runs = api("GET", f"/repos/{repo}/actions/workflows/{wf['id']}/runs?event=schedule&per_page=1", token)
        # বাংলা: API failure মানে "কখনও schedule চলেনি" নয়; প্রমাণ ছাড়া mutation বন্ধ।
        if code != 200 or not isinstance(runs, dict) or not isinstance(runs.get("workflow_runs"), list):
            report.append(f"WARN(schedule evidence unavailable {code}) | {path}")
            evidence_missing = True
            continue
        last_sched = (runs["workflow_runs"] or [{}])[0].get("created_at")
        if last_sched:
            last_dt = dt.datetime.fromisoformat(last_sched.replace("Z", "+00:00"))
        else:
            last_dt = None

        # শেষ যেকোনো-ইভেন্ট রান
        code2, runs2 = api("GET", f"/repos/{repo}/actions/workflows/{wf['id']}/runs?per_page=1", token)
        if code2 != 200 or not isinstance(runs2, dict) or not isinstance(runs2.get("workflow_runs"), list):
            report.append(f"WARN(activity evidence unavailable {code2}) | {path}")
            evidence_missing = True
            continue
        last_any = (runs2["workflow_runs"] or [{}])[0].get("created_at")
        last_any_dt = (
            dt.datetime.fromisoformat(last_any.replace("Z", "+00:00")) if last_any else None
        )

        dead = False
        next_due = None
        for cron in crons:
            try:
                base = last_dt or (now - dt.timedelta(days=400))
                due = cron_next(cron, base)
            except Exception:
                continue
            if next_due is None or due < next_due:
                next_due = due
        if next_due is not None:
            dead = now > next_due + dt.timedelta(minutes=GRACE_MIN)
        elif last_dt is None:
            dead = True  # cron আছে, কিন্তু জীবনেও schedule-run নেই

        status = "DEAD" if dead else "ok"
        line = (
            f"{status} | {path} | cron={crons} | lastSchedule={last_sched or 'never'} "
            f"| nextDue={next_due.isoformat() if next_due else '?'}"
        )

        if dead and args.dry_run:
            line += " | (dry-run: re-arm+compensate হত)"
        elif dead:
            # ১) প্রমাণ নিশ্চিত না করে re-arm বা dispatch করা যাবে না।
            can_dispatch = isinstance(trig or {}, dict) and "workflow_dispatch" in (trig or {})
            # আমরা এখানে `if dead`-এর ভেতরে — তাই compensation-এর শর্ত: শেষ যেকোনো-ইভেন্ট
            # রানও grace-এর চেয়ে বাসি (recent dispatch/PR রান থাকলে দ্বৈত চালানো বৃথা)।
            stale_any = last_any_dt is not None and now > last_any_dt + dt.timedelta(minutes=GRACE_MIN)
            # E11: check-before-dispatch — already queued বা running run থাকলে নতুন dispatch দিয়ে queue storm বানাবে না
            code_q, runs_q = api("GET", f"/repos/{repo}/actions/workflows/{wf['id']}/runs?status=queued&per_page=1", token)
            code_r, runs_r = api("GET", f"/repos/{repo}/actions/workflows/{wf['id']}/runs?status=in_progress&per_page=1", token)
            # বাংলা: queue/running অবস্থা অজানা বা সক্রিয় থাকলে কোনো mutation নয়।
            queue_known = (code_q == 200 and isinstance(runs_q, dict)
                           and isinstance(runs_q.get("workflow_runs"), list))
            running_known = (code_r == 200 and isinstance(runs_r, dict)
                             and isinstance(runs_r.get("workflow_runs"), list))
            busy = (bool(runs_q["workflow_runs"]) if queue_known else False) or (
                bool(runs_r["workflow_runs"]) if running_known else False
            )
            state_unknown = not (queue_known and running_known)
            if state_unknown:
                evidence_missing = True
                report.append(line + " | comp=skipped(queue-state-unavailable)")
                continue
            if busy:
                report.append(line + " | comp=skipped(already-queued-or-running)")
                continue

            # ২) re-arm: disable → enable (cron re-registration)।
            c1, _ = api("PUT", f"/repos/{repo}/actions/workflows/{wf['id']}/disable", token)
            c2, _ = api("PUT", f"/repos/{repo}/actions/workflows/{wf['id']}/enable", token)
            armed = c1 == 204 and c2 == 204
            if armed:
                re_armed += 1
            else:
                # বাংলা: enable ব্যর্থ হলেও success ঘোষণা নয়; operator-কে সতর্ক করো।
                evidence_missing = True
            line += f" | re-arm={armed}({c1}/{c2})"

            if can_dispatch and stale_any and armed:
                c3, _ = api(
                    "POST",
                    f"/repos/{repo}/actions/workflows/{wf['id']}/dispatches",
                    token,
                    {"ref": default_branch},
                )
                if c3 == 204:
                    compensated += 1
                    line += f" | compensated(dispatch {c3})"
                else:
                    evidence_missing = True
                    line += f" | dispatch-failed({c3})"
            elif not can_dispatch:
                line += " | comp=skipped(no-dispatch)"
            else:
                line += " | comp=skipped(recent-activity)"
        report.append(line)

    print("WATCHDOG sweep report (UTC {})".format(now.isoformat(timespec="seconds")))
    for ln in report:
        print("  " + ln)
    print(f"WATCHDOG summary: re_armed={re_armed} compensated={compensated} dry_run={args.dry_run}")
    if evidence_missing:
        print("WATCHDOG: evidence unavailable or self-heal failed; inspect the report", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
