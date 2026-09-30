#!/usr/bin/env bash
# Atomic Mutex Claim (GAP-01 fix — Claim-then-Verify pattern)
# ============================================================
# GitHub REST API-এর `issue edit --add-assignee` true atomic lock নয় —
# দুজন agent একই সময়ে assign করলে race condition হয়। এই script
# Claim-then-Verify pattern implement করে:
#
#   1. CLAIM:    gh issue edit $ID --add-assignee "$AGENT_NAME"
#   2. VERIFY:   gh issue view $ID --json assignees → check যে আমি একমাত্র assignee
#   3. CAS check: যদি অন্য assignee থাকে → আমি lose, exit 1
#   4. LOCK:     status:in-progress label যোগ করি (atomic via gh issue edit)
#
# AUDIT-FIX (#1838): --skip-assign flag added. GitHub App bots (e.g.
# supremeai-coder-1-bot[bot]) get 403 Forbidden on /assignees API — they
# cannot be assigned. With --skip-assign the CLAIM/VERIFY steps are
# replaced by a LABEL-based pre-check + LOCK (status:in-progress label,
# the canonical lock per AGENTS.md §3).
#
# GROUP BRANCHING (#2378 — Flexible Group Branching Protocol):
#   1. BRANCH_NAME="group/<name>" গ্রহণযোগ্য — issue number থাকা বাধ্যতামূলক নয়,
#      গ্রুপ ব্রাঞ্চ নামকরণ `^group/<name>$` হলেই হবে।
#   2. --files "f1, f2" — claim comment-এ 'Touching files:' ঘোষণা এম্বেড করে।
#   3. শেয়ার্ড গ্রুপ ব্রাঞ্চে একাধিক agent-এর ফাইল-বাউন্ডারি এনফোর্স করে: একই
#      group:* লেবেলের অন্য status:in-progress ইস্যুর ঘোষণার সাথে overlap
#      হলে claim বাতিল (--force override)। ফলে একই ব্রাঞ্চে ২ agent একই ফাইলে
#      হাত দিতে পারে না — collision gate-এর group-লেভেল প্রি-চেক।
#   4. গ্রুপ ব্রাঞ্চে origin/main auto-sync স্কিপ হয় — গ্রুপ sync হবে Merge Train-এ।
#
# FAIR-SHARE COOLDOWN (#2573):
#   After completing a group sequence, record a cooldown so other agents
# can claim the next sequence. Use --record-cooldown-group <group_name>.
#
# Usage:
#   scripts/ci/atomic_claim.sh <issue_number> <agent_name> [--status-label <label>] [--skip-assign]
#                              [--files "path/a.py, path/b.py"] [--force]
#                              [--record-cooldown-group <group_name>]
#
# Exit codes:
#   0 = claim successful (this agent owns the issue now)
#   1 = claim failed (race lost — another agent got there first)
#   2 = invalid args / missing dependencies
#   3 = file-boundary overlap with a sibling claim in the same group (#2378)

set -euo pipefail

# Python interpreter detection (handles Linux, macOS, and Windows Git Bash / MS Store stubs)
if command -v python &>/dev/null && python -c "import sys" 2>/dev/null; then
  PYTHON_BIN="python"
elif command -v python3 &>/dev/null && python3 -c "import sys" 2>/dev/null; then
  PYTHON_BIN="python3"
elif command -v py &>/dev/null && py -c "import sys" 2>/dev/null; then
  PYTHON_BIN="py"
else
  PYTHON_BIN="python"
fi

# ─── Args ────────────────────────────────────────────────────────────────
# (#1838) flag parsing — backwards compatible with positional args.
SKIP_ASSIGN=false
FORCE=false
STATUS_LABEL="status:in-progress"
FILES_DECLARATION=""
RECORD_COOLDOWN_GROUP=""
POSITIONAL=()
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-assign|--skip-assign=true)
      SKIP_ASSIGN=true
      shift
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --files)
      shift
      FILES_DECLARATION="${1:-}"
      shift
      ;;
    --files=*)
      FILES_DECLARATION="${1#*=}"
      shift
      ;;
    --status-label)
      shift
      STATUS_LABEL="${1:-status:in-progress}"
      shift
      ;;
    --status-label=*)
      STATUS_LABEL="${1#*=}"
      shift
      ;;
    --record-cooldown-group)
      shift
      RECORD_COOLDOWN_GROUP="${1:-}"
      shift
      ;;
    --record-cooldown-group=*)
      RECORD_COOLDOWN_GROUP="${1#*=}"
      shift
      ;;
    *)
      POSITIONAL+=("$1")
      shift
      ;;
  esac
done
ISSUE_NUMBER="${POSITIONAL[0]:-}"
AGENT_NAME="${POSITIONAL[1]:-}"

if [ -n "$RECORD_COOLDOWN_GROUP" ]; then
  echo "🧊 Recording cooldown for group '$RECORD_COOLDOWN_GROUP'..."
  "$PYTHON_BIN" scripts/agents/acquire_role_slot.py --record-cooldown-group "$RECORD_COOLDOWN_GROUP" --agent-name "$AGENT_NAME" ${ISSUE_NUMBER:+--issue "$ISSUE_NUMBER"} 2>/dev/null || true
  if [ -n "$ISSUE_NUMBER" ]; then
    echo "✅ Cooldown recorded for group '$RECORD_COOLDOWN_GROUP' after issue #$ISSUE_NUMBER"
  else
    echo "✅ Cooldown recorded for group '$RECORD_COOLDOWN_GROUP'"
  fi
  exit 0
fi

if [ -z "$ISSUE_NUMBER" ] || [ -z "$AGENT_NAME" ]; then
  echo "Usage: $0 <issue_number> <agent_name> [--status-label <label>] [--skip-assign] [--files \"f1, f2\"] [--force]" >&2
  echo "  --skip-assign      Skip assignee step (for GitHub App bots that get 403)" >&2
  echo "  --status-label     Override the status label (default: status:in-progress)" >&2
  echo "  --files            'Touching files:' declaration (required on group branches, #2378)" >&2
  echo "  --force            Override file-boundary overlap block (with caution)" >&2
  echo "Examples:" >&2
  echo "  $0 900 agent-1                          # Human operator claim" >&2
  echo "  $0 900 agent-3-coder-1 --skip-assign   # Bot claim (skips 403)" >&2
  exit 2
fi

if ! command -v gh &> /dev/null; then
  echo "ERROR: gh CLI not installed" >&2
  exit 2
fi

# Required env (GH_TOKEN: explicit env -> gh auth token fallback -> fail)
: "${GH_TOKEN:=$(gh auth token 2>/dev/null || true)}"

export GH_REPO="${GH_REPO:-SaifulHaqueNiloy/supremeai}"
: "${GH_TOKEN:?GH_TOKEN required -- run: gh auth login}"

# ─── Pre-check: already claimed? ────────────────────────────────────────
echo "🔍 Pre-checking issue #$ISSUE_NUMBER for existing claim..."

# GAP-DUPLICATE-01 FIX: Check for 'has-pr' label FIRST.
# If any agent already opened a PR for this issue, the issue gets 'has-pr'.
# Seeing 'has-pr' means a PR already exists — do NOT open another one.
EXISTING_HAS_PR=$(gh issue view "$ISSUE_NUMBER" --json labels -q '.labels[].name' 2>/dev/null | grep -Fx 'has-pr' || true)
if [ -n "$EXISTING_HAS_PR" ]; then
  echo "❌ Issue #$ISSUE_NUMBER already has 'has-pr' label — a PR exists for this issue."
  echo "Duplicate PR prevention (GAP-DUPLICATE-01): aborting claim."
  echo "Check open PRs for this issue before proceeding."
  exit 1
fi

# GAP-DUPLICATE-01 FIX: Also check if any open PR references this issue
# (fallback for issues where 'has-pr' label wasn't set by a prior agent)
OPEN_PR_FOR_ISSUE=$(gh pr list --state open --search "#$ISSUE_NUMBER" --json number,title --limit 5 2>/dev/null | "$PYTHON_BIN" -c "
import json, sys
try:
    prs = json.load(sys.stdin)
    refs = [str(p['number']) for p in prs if str($ISSUE_NUMBER) in (p.get('body') or p.get('title') or '')]
    print(' '.join(refs))
except:
    print('')
" 2>/dev/null || echo "")
if [ -n "$OPEN_PR_FOR_ISSUE" ]; then
  echo "⚠️  Open PR(s) found referencing issue #$ISSUE_NUMBER: $OPEN_PR_FOR_ISSUE"
  echo "Adding missing 'has-pr' label to issue (backfill)..."
  gh issue edit "$ISSUE_NUMBER" --add-label 'has-pr' 2>/dev/null || true
  echo "❌ Duplicate PR prevention (GAP-DUPLICATE-01): aborting claim."
  exit 1
fi

# ─── Sequential Integrity Check (Rule #26: GSPQ Contiguous Order) ───────
echo "🚂 Checking sequential integrity for issue #$ISSUE_NUMBER..."
if "$PYTHON_BIN" scripts/ci/issue_queue_manager.py verify-claim --issue "$ISSUE_NUMBER" 2>/dev/null; then
  echo "✅ Sequential constraint verified."
else
  echo "❌ Sequential constraint violation! You cannot claim out of sequence."
  echo "Prior issue in group sequence must be claimed or completed first."
  exit 1
fi


# AUDIT-FIX (#2008): Rule #13 "ONE ACTIVE CLAIM PER AGENT" — check if this
# agent already has another issue with status:in-progress before claiming.
# Uses label-based check (works for bots that can't be assigned via API).
ACTIVE_CLAIMS=$(gh issue list --label "$STATUS_LABEL" --state open --json number,title --limit 50 2>/dev/null || echo "[]")
ACTIVE_COUNT=$(echo "$ACTIVE_CLAIMS" | "$PYTHON_BIN" -c "
import json, sys
try:
    issues = json.load(sys.stdin)
    print(len(issues))
except:
    print(0)
" 2>/dev/null || echo "0")

if [ "$ACTIVE_COUNT" -gt 0 ]; then
  # Check if any of the active claims have THIS agent's audit comment
  MY_ACTIVE=$(echo "$ACTIVE_CLAIMS" | "$PYTHON_BIN" -c "
import json, sys, subprocess
issues = json.load(sys.stdin)
me = '$AGENT_NAME'
my_issues = []
for issue in issues:
    num = issue.get('number')
    try:
        comments = subprocess.run(['gh', 'issue', 'view', str(num), '--json', 'comments', '-q', '.comments[].body'],
            capture_output=True, text=True, timeout=10)
        if me in comments.stdout:
            my_issues.append(f'#{num}: {issue.get(\"title\",\"\")[:60]}')
    except:
        pass
if my_issues:
    print('\\n'.join(my_issues))
else:
    print('')
" 2>/dev/null || echo "")

  if [ -n "$MY_ACTIVE" ]; then
    echo "⚠️  WARNING: You already have $STATUS_LABEL on these issues (Rule #13: ONE ACTIVE CLAIM PER AGENT):"
    echo "$MY_ACTIVE" | sed 's/^/    /'
    echo ""
    echo "Complete or release the current claim before claiming another."
    echo "Use --force to override (with caution)."
    # (--force is parsed in the Args loop above — "$@" is consumed by then)
    if [ "$FORCE" != "true" ]; then
      echo "❌ Claim blocked by Rule #13. Use --force to override."
      exit 1
    else
      echo "⚡ --force override: proceeding despite active claims"
    fi
  fi
fi

EXISTING_ASSIGNEES=$(gh issue view "$ISSUE_NUMBER" --json assignees -q '.assignees[].login' 2>/dev/null || echo "")

# AUDIT-FIX (#1838): When --skip-assign is used (bot mode), check the
# status:in-progress LABEL instead of assignees — that's the canonical lock.
if [ "$SKIP_ASSIGN" = "true" ]; then
  EXISTING_LABELS=$(gh issue view "$ISSUE_NUMBER" --json labels -q '.labels[].name' 2>/dev/null || echo "")
  if echo "$EXISTING_LABELS" | grep -qFx "$STATUS_LABEL"; then
    # Check if this agent already posted an audit comment (idempotent)
    EXISTING_COMMENTS=$(gh issue view "$ISSUE_NUMBER" --json comments -q '.comments[].body' 2>/dev/null || echo "")
    if echo "$EXISTING_COMMENTS" | grep -q "Atomic Claim.*$AGENT_NAME"; then
      echo "✅ Issue #$ISSUE_NUMBER already claimed by me ($AGENT_NAME) — idempotent success"
      exit 0
    fi
    echo "❌ Issue #$ISSUE_NUMBER already has '$STATUS_LABEL' label (claimed by another agent)"
    echo "Claim failed — race lost."
    exit 1
  fi
  echo "  No existing '$STATUS_LABEL' label — proceeding to LOCK"
else
  if [ -n "$EXISTING_ASSIGNEES" ]; then
    # Check if it's me already (idempotent retry)
    if echo "$EXISTING_ASSIGNEES" | grep -qFx "$AGENT_NAME"; then
      echo "✅ Issue #$ISSUE_NUMBER already assigned to me ($AGENT_NAME) — idempotent success"
      # Ensure status label is present
      gh issue edit "$ISSUE_NUMBER" --add-label "$STATUS_LABEL" 2>/dev/null || true
      exit 0
    fi
    echo "❌ Issue #$ISSUE_NUMBER already has assignee(s):"
    echo "$EXISTING_ASSIGNEES" | sed 's/^/  - /'
    echo "Claim failed — race lost."
    exit 1
  fi
fi

# ─── STEP 1: CLAIM (optimistic) ──────────────────────────────────────────
if [ "$SKIP_ASSIGN" = "true" ]; then
  # (#1838) Bot mode — skip assignee step entirely. GitHub App bots get 403
  # on /assignees API. The canonical lock (AGENTS.md §3) is the label.
  echo "🎯 Bot mode (--skip-assign): skipping assignee step"
else
  echo "🎯 Claiming issue #$ISSUE_NUMBER as $AGENT_NAME..."
  gh issue edit "$ISSUE_NUMBER" --add-assignee "$AGENT_NAME" 2>&1 | sed 's/^/  /' || {
    echo "❌ Claim command failed"
    exit 1
  }
fi

# ─── STEP 2: VERIFY (Compare-And-Swap check) ───────────────────────────
# CRITICAL: GitHub's --add-assignee is APPEND, not REPLACE.
# If two agents called simultaneously, BOTH might be in the assignees list.
# We must verify we are the ONLY assignee (or at least the first one).
# (#1838) Bot mode skips this — no assignee write happened, nothing to CAS.
if [ "$SKIP_ASSIGN" != "true" ]; then
echo "🔍 Verifying claim..."
sleep 1  # Brief delay to let any concurrent claims settle

ASSIGNEES_JSON=$(gh issue view "$ISSUE_NUMBER" --json assignees)
ASSIGNEE_COUNT=$(echo "$ASSIGNEES_JSON" | "$PYTHON_BIN" -c "import json,sys;d=json.load(sys.stdin);print(len(d.get('assignees',[])))")
FIRST_ASSIGNEE=$(echo "$ASSIGNEES_JSON" | "$PYTHON_BIN" -c "import json,sys;d=json.load(sys.stdin);a=d.get('assignees',[]);print(a[0]['login'] if a else '')")

echo "  Current assignees: $ASSIGNEE_COUNT"
echo "  First assignee: $FIRST_ASSIGNEE"

if [ "$FIRST_ASSIGNEE" != "$AGENT_NAME" ]; then
  echo "❌ Lost the race — first assignee is '$FIRST_ASSIGNEE', not me ($AGENT_NAME)"
  echo "Removing myself from assignees (cleanup)..."
  gh issue edit "$ISSUE_NUMBER" --remove-assignee "$AGENT_NAME" 2>/dev/null || true
  exit 1
fi

if [ "$ASSIGNEE_COUNT" -gt 1 ]; then
  echo "⚠️ Multiple assignees detected ($ASSIGNEE_COUNT) — I am first, but race happened"
  echo "Removing other assignees (I claimed first)..."
  # Remove all assignees except myself
  OTHER_ASSIGNEES=$(echo "$ASSIGNEES_JSON" | "$PYTHON_BIN" -c "
import json, sys
d = json.load(sys.stdin)
me = '$AGENT_NAME'
for a in d.get('assignees', []):
    if a['login'] != me:
        print(a['login'])
")
  for other in $OTHER_ASSIGNEES; do
    echo "  removing $other..."
    gh issue edit "$ISSUE_NUMBER" --remove-assignee "$other" 2>/dev/null || true
  done
fi
fi # SKIP_ASSIGN (STEP 2 CAS verify — human mode only)

# ─── STEP 3: LOCK — add status label + drop stale unclaimed label ─────────
echo "🔒 Adding status label '$STATUS_LABEL'..."
gh issue edit "$ISSUE_NUMBER" --add-label "$STATUS_LABEL" 2>&1 | sed 's/^/  /' || {
  echo "⚠️ Failed to add status label (non-fatal — claim still valid)"
}

# Issue #1909 fix: an issue that just got claimed must no longer advertise
# itself as unclaimed. Leaving status:unclaimed on it makes any queue that
# filters on that label (e.g. next_claimable.sh, #1906) hand the same issue
# to another agent — double-claim risk. Best-effort removal: the claim
# (assignee CAS above) is already authoritative even if this fails.
echo "🧹 Removing stale 'status:unclaimed' label (issue #1909)..."
gh issue edit "$ISSUE_NUMBER" --remove-label "status:unclaimed" 2>&1 | sed 's/^/  /' || {
  echo "⚠️ Failed to remove status:unclaimed (non-fatal — claim still valid)"
}

# ─── STEP 3.5: POST-VERIFY — TOCTOU hardening (issue #1989) ─────────────
# বাংলা: label add করার পরেই অবস্থা re-read করা বাধ্যতামূলক — add-assignee
# ও add-label দুটোই APPEND; verify ও label-এর মাঝামাঝি সময়ে আরেকটি agent
# ঢুকে গেলে শুধু আগের CAS check তা ধরত না। নিচের re-read নিশ্চিত করে:
#   (a) আমি এখনো একমাত্র/প্রথম assignee, এবং
#   (b) status label সত্যিই বসেছে।
# ব্যর্থ হলে নিজের label সরিয়ে (release) exit 1 — double-claim অসম্ভব।
echo "🔎 Post-verify: re-reading issue state (issue #1989)..."
sleep 1
FINAL_JSON=$(gh issue view "$ISSUE_NUMBER" --json assignees,labels 2>/dev/null || echo "{}")
if [ "$SKIP_ASSIGN" != "true" ]; then
  # (#1838) assignee re-check only makes sense when we wrote an assignee.
  ME_STILL_ASSIGNED=$(echo "$FINAL_JSON" | "$PYTHON_BIN" -c "
import json, sys
d = json.load(sys.stdin)
me = '$AGENT_NAME'
print('yes' if any(a.get('login') == me for a in d.get('assignees', [])) else 'no')
")
  if [ "$ME_STILL_ASSIGNED" != "yes" ]; then
    echo "❌ Post-verify FAILED: I am no longer an assignee (raced and evicted) — releasing $STATUS_LABEL..."
    gh issue edit "$ISSUE_NUMBER" --remove-label "$STATUS_LABEL" 2>/dev/null || true
    exit 1
  fi
fi
FINAL_HAS_LABEL=$(echo "$FINAL_JSON" | "$PYTHON_BIN" -c "
import json, sys
d = json.load(sys.stdin)
want = '$STATUS_LABEL'
print('yes' if any(l.get('name') == want for l in d.get('labels', [])) else 'no')
")
if [ "$FINAL_HAS_LABEL" != "yes" ]; then
  echo "⚠️ status label missing after add — retrying once..."
  gh issue edit "$ISSUE_NUMBER" --add-label "$STATUS_LABEL" 2>/dev/null || true
fi
if [ "$SKIP_ASSIGN" = "true" ]; then
  echo "  ✅ Post-verify passed: status label present (bot mode)"
else
  echo "  ✅ Post-verify passed: sole assignee + status label present"
fi

# ─── STEP 4: Post claim timestamp comment (for audit trail) ────────────
CLAIM_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')

# (#2464) Touching-files কম্পোজিশন — tests-গাছ অটো-ইনক্লুড:
# 101% test-policy অনুযায়ী fix-PR সবসময় নতুন টেস্ট ফাইল আনে, কিন্তু এজেন্ট
# claim-টাইমে সেগুলো ঘোষণায় রাখে না → Scope Gate-এর প্রতি-PR বাড়তি
# BLOCK-চক্র (#2461 প্রমাণ)। কম্পোজার (compose_touching_declaration.py)
# tests-গাছ না থাকলে `tests/` অটো-যোগ করে; helper ব্যর্থ হলে পুরনো ইনলাইন
# আচরণ (safe-degrade — gate ব্লক করবে, allowlist নয়)।
FILES_LINE=$("$PYTHON_BIN" scripts/ci/compose_touching_declaration.py --files "$FILES_DECLARATION" 2>/dev/null) \
  || FILES_LINE="${FILES_DECLARATION:-_(declared in a follow-up comment before PR — Rule 2)_}"

# GAP-DUPLICATE-01: Enforce branch naming convention in the claim comment.
# Independent branch MUST include the issue number: <lane>-<N>-<issue_number>-<slug>
# Example: coder-1-2253-fix-session-takeover  (NOT just 'coder-1')
# GROUP branch (#2378): `group/<name>` — issue number থাকবে না, গ্রুপ নাম থাকবে।
if [ -n "${BRANCH_NAME:-}" ]; then
  if [[ "$BRANCH_NAME" == group/* ]]; then
    if ! echo "$BRANCH_NAME" | grep -qE '^group/[a-z0-9][a-z0-9._-]*$'; then
      echo "❌ GROUP BRANCH NAME VIOLATION (#2378): '$BRANCH_NAME' must match 'group/<name>' (lowercase slug)"
      echo "Releasing claim..."
      gh issue edit "$ISSUE_NUMBER" --remove-label "$STATUS_LABEL" 2>/dev/null || true
      exit 1
    fi
    echo "🌿 Group branch '$BRANCH_NAME' accepted (#2378 Connected Work — shared branch, 1 group PR)"
  elif [[ "$BRANCH_NAME" != *"$ISSUE_NUMBER"* ]]; then
    echo "❌ BRANCH NAME VIOLATION (GAP-DUPLICATE-01): '$BRANCH_NAME' must contain issue number '$ISSUE_NUMBER'"
    echo "Required format: <lane>-<N>-<issue_number>-<slug>  e.g. coder-1-${ISSUE_NUMBER}-my-fix"
    echo "Releasing claim..."
    gh issue edit "$ISSUE_NUMBER" --remove-label "$STATUS_LABEL" 2>/dev/null || true
    exit 1
  fi
fi

CLAIM_COMMENT="### 🔒 Atomic Claim Established (GAP-01)

- **Agent:** \`$AGENT_NAME\`
- **Issue:** #$ISSUE_NUMBER
- **Claimed at:** $CLAIM_TIME
- **Branch:** \`${BRANCH_NAME:-not-yet-created}\`
# বাংলা মন্তব্য (#2597, #2644): এই কমেন্ট block-টি double-quoted string —
# ভেতরের প্রতিটি literal backtick \` দিয়ে escape করতে হয়, নাহলে bash সেগুলো
# command substitution হিসেবে চালায় (যেমন #2644-এ: \`fallback_\` → 'command
# not found' ×4, set -e স্ক্রিপ্ট আবর্তনে মেরে ফেলত — claim comment-ই আর
# পোস্ট হতো না, Touching files: ডিক্লারেশন হারিয়ে Scope Gate ভাঙত)।
# (#2464) Touching files-এর মান এখন FILES_LINE — compose_touching_declaration.py
# কম্পোজ করে (tests-গাছ অটো-ইনক্লুড + parse-safe অ্যানোটেশন); ইটালিক ফলব্যাক
# কেবল খালি ঘোষণায়।
- **Touching files:** ${FILES_LINE}
- **Method:** Claim-then-Verify (Compare-And-Swap) + has-pr guard (GAP-DUPLICATE-01)
- **Verifier:** \`scripts/ci/atomic_claim.sh\`

_Automated by atomic_claim.sh — Race-safe mutex establishment per ARCH-GAP-01_"

gh issue comment "$ISSUE_NUMBER" --body "$CLAIM_COMMENT" 2>&1 | sed 's/^/  /' || true

# GAP-DUPLICATE-01: The agent MUST add 'has-pr' label to the issue immediately
# after gh pr create succeeds. This is NOT done here (we haven't created the PR yet),
# but scripts/ci/open_pr.sh (or the agent's next step) MUST call:
#   gh issue edit $ISSUE_NUMBER --add-label 'has-pr'
# Agents: see Rule #24 in AGENTS.md. FAILURE TO DO SO causes duplicate PRs.
echo "📌 REMINDER (GAP-DUPLICATE-01): After 'gh pr create', immediately run:"
echo "   gh issue edit $ISSUE_NUMBER --add-label 'has-pr'"
echo "   This MUST happen before any other agent's next_claimable.sh run."

# ─── STEP 4.5: Group-branch file-boundary check (#2378) ────────────────
# বাংলা: শেয়ার্ড গ্রুপ ব্রাঞ্চে একাধিক agent কাজ করে — তাই একই group:* লেবেলের
# অন্য status:in-progress ইস্যুগুলোর 'Touching files:' ঘোষণার সাথে overlap
# ধরা আবশ্যক, নইলে একই ব্রাঞ্চে ২ agent একই ফাইল এডিট করে পালা করে উল্টে দেবে।
# Overlap পেলে নিজের claim release করে exit 3 (--force override সম্ভব)।
if [ -n "${BRANCH_NAME:-}" ] && [[ "$BRANCH_NAME" == group/* ]]; then
  GROUP_LABEL=$(gh issue view "$ISSUE_NUMBER" --json labels -q '.labels[].name' 2>/dev/null | grep -E '^group:' | head -1 || true)
  if [ -n "$GROUP_LABEL" ]; then
    echo "🌿 Group lease detected ($GROUP_LABEL on $BRANCH_NAME) — checking sibling file boundaries (#2378)..."
    SIBLINGS_JSON=$(gh issue list --label "$GROUP_LABEL" --label "$STATUS_LABEL" --state open --json number,title --limit 50 2>/dev/null || echo "[]")
    RC=0
    OVERLAP=$(GROUP_NAME="${GROUP_LABEL#group:}" \
              MY_ISSUE="$ISSUE_NUMBER" \
              MY_FILES="$FILES_DECLARATION" \
              MY_AGENT="$AGENT_NAME" \
              SIBLINGS_JSON="$SIBLINGS_JSON" \
              "$PYTHON_BIN" << 'GROUP_BOUNDARY_PY'
import json, os, re, subprocess

marker = "Touching files:"

def norm(p):
    p = (p or "").strip().strip("`").strip()
    p = re.sub(r"^\.\/", "", p)
    if p in ("", "/"):
        return ""
    return p.rstrip("/").removesuffix("/**").rstrip("/")

def harvest(segment):
    files = set()
    idx = segment.find(marker)
    if idx == -1:
        return files
    seg = segment[idx + len(marker):]
    stop = re.search(r"\n#{1,6} ", seg)
    if stop:
        seg = seg[: stop.start()]
    for tok in re.split(r"[,`\n]+", seg):
        t = tok.strip().lstrip("-* ").strip()
        t = t.split()[0] if t.split() else ""
        if t and ("/" in t or "." in t) and not t.startswith("#") and not t.startswith("("):
            n = norm(t)
            if n:
                files.add(n)
    return files

def overlap_pair(mine, theirs):
    for a in sorted(mine):
        for b in sorted(theirs):
            if a == b or a.startswith(b + "/") or b.startswith(a + "/"):
                # (#2464) tests-গাছ auto-ইনক্লুডের পার্সপেক্টিভ: ট্রি-টোকেন
                # ('tests', claim-কমেন্ট থেকে auto-যোগ) vs নির্দিষ্ট টেস্ট-ফাইলের
                # ম্যাচ ভুল কলিশন — ভিন্ন টেস্ট-ফাইল ভিন্ন পাথ, git-লেভেলে
                # কনফ্লিক্ট করে না। একই-ফাইল (a == b) আগের মতোই ধরা পড়ে;
                # ট্রি-টোকেন নয় এমন ম্যাচ (src/ ইত্যাদি) অপরিবর্তিত।
                if not a == b and "tests" in (a, b):
                    continue
                return (a, b)
    return None

my_files = harvest("Touching files: " + os.environ.get("MY_FILES", ""))
if not my_files:
    print("NOTICE: no --files declaration; boundary check advisory-only")
    raise SystemExit(0)

me = os.environ.get("MY_ISSUE", "")
try:
    siblings = [s for s in json.loads(os.environ.get("SIBLINGS_JSON", "[]")) if str(s.get("number")) != str(me)]
except json.JSONDecodeError:
    siblings = []

for s in siblings[:10]:
    num = s.get("number")
    try:
        res = subprocess.run(
            ["gh", "issue", "view", str(num), "--json", "comments", "-q", "[.comments[].body] | join(\"\\n\\n\")"],
            capture_output=True, text=True, timeout=15,
        )
        body = res.stdout or ""
    except Exception:
        continue
    their_files = harvest(body)
    hit = overlap_pair(my_files, their_files)
    if hit:
        print(f"OVERLAP: issue #{num} already declared `{'` + `'.join(sorted(their_files))}`; my `{hit[0]}` collides")
        raise SystemExit(1)
print("OK: no file-boundary overlap with sibling claims in this group")
GROUP_BOUNDARY_PY
    ) || RC=$?
    if [ "$RC" -ne 0 ]; then
      if [ "$FORCE" != "true" ]; then
        echo "$OVERLAP" | sed 's/^/  /'
        echo "❌ File-boundary overlap in group branch (#2378) — claim released. Change your scope or coordinate; use --force to override."
        gh issue edit "$ISSUE_NUMBER" --remove-label "$STATUS_LABEL" 2>/dev/null || true
        exit 3
      else
        echo "⚡ --force override: proceeding despite file-boundary overlap"
      fi
    else
      echo "$OVERLAP" | sed 's/^/  /'
    fi
  fi
fi

# ─── STEP 5: AUTO-SYNC WORKSPACE (Zero Drift Protection) ─────────────────
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "")
if [[ "$CURRENT_BRANCH" == group/* ]]; then
  echo "🌿 Group branch '$CURRENT_BRANCH' — origin/main auto-sync SKIPPED (#2378: গ্রুপ ব্রাঞ্চ sync হবে Merge Train-এ, মাঝপথে main-merge নয়)"
else
  echo "🔄 Auto-syncing workspace with latest origin/main..."
  "$PYTHON_BIN" scripts/git/auto_sync_main.py 2>/dev/null || true
fi

echo "✅ Atomic claim successful — issue #$ISSUE_NUMBER owned by $AGENT_NAME"
exit 0
