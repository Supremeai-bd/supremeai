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
# Usage:
#   scripts/ci/atomic_claim.sh <issue_number> <agent_name> [--status-label status:in-progress]
#
# Exit codes:
#   0 = claim successful (this agent owns the issue now)
#   1 = claim failed (race lost — another agent got there first)
#   2 = invalid args / missing dependencies

set -euo pipefail

# ─── Args ────────────────────────────────────────────────────────────────
ISSUE_NUMBER="${1:-}"
AGENT_NAME="${2:-}"
STATUS_LABEL="${3:-status:in-progress}"

if [ -z "$ISSUE_NUMBER" ] || [ -z "$AGENT_NAME" ]; then
  echo "Usage: $0 <issue_number> <agent_name> [status_label]" >&2
  echo "Example: $0 900 agent-1" >&2
  exit 2
fi

if ! command -v gh &> /dev/null; then
  echo "ERROR: gh CLI not installed" >&2
  exit 2
fi

# Required env
: "${GH_TOKEN:?GH_TOKEN env var required}"
: "${GH_REPO:?GH_REPO env var required}"

# ─── Pre-check: already claimed? ────────────────────────────────────────
echo "🔍 Pre-checking issue #$ISSUE_NUMBER for existing assignees..."
EXISTING_ASSIGNEES=$(gh issue view "$ISSUE_NUMBER" --json assignees -q '.assignees[].login' 2>/dev/null || echo "")

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

# ─── STEP 1: CLAIM (optimistic) ──────────────────────────────────────────
echo "🎯 Claiming issue #$ISSUE_NUMBER as $AGENT_NAME..."
gh issue edit "$ISSUE_NUMBER" --add-assignee "$AGENT_NAME" 2>&1 | sed 's/^/  /' || {
  echo "❌ Claim command failed"
  exit 1
}

# ─── STEP 2: VERIFY (Compare-And-Swap check) ───────────────────────────
# CRITICAL: GitHub's --add-assignee is APPEND, not REPLACE.
# If two agents called simultaneously, BOTH might be in the assignees list.
# We must verify we are the ONLY assignee (or at least the first one).
echo "🔍 Verifying claim..."
sleep 1  # Brief delay to let any concurrent claims settle

ASSIGNEES_JSON=$(gh issue view "$ISSUE_NUMBER" --json assignees)
ASSIGNEE_COUNT=$(echo "$ASSIGNEES_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin);print(len(d.get('assignees',[])))")
FIRST_ASSIGNEE=$(echo "$ASSIGNEES_JSON" | python3 -c "import json,sys;d=json.load(sys.stdin);a=d.get('assignees',[]);print(a[0]['login'] if a else '')")

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
  OTHER_ASSIGNEES=$(echo "$ASSIGNEES_JSON" | python3 -c "
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

# ─── STEP 3: LOCK — add status label ────────────────────────────────────
echo "🔒 Adding status label '$STATUS_LABEL'..."
gh issue edit "$ISSUE_NUMBER" --add-label "$STATUS_LABEL" 2>&1 | sed 's/^/  /' || {
  echo "⚠️ Failed to add status label (non-fatal — claim still valid)"
}

# ─── STEP 4: Post claim timestamp comment (for audit trail) ────────────
CLAIM_TIME=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
CLAIM_COMMENT="### 🔒 Atomic Claim Established (GAP-01)

- **Agent:** \`$AGENT_NAME\`
- **Issue:** #$ISSUE_NUMBER
- **Claimed at:** $CLAIM_TIME
- **Method:** Claim-then-Verify (Compare-And-Swap)
- **Verifier:** \`scripts/ci/atomic_claim.sh\`

_Automated by atomic_claim.sh — Race-safe mutex establishment per ARCH-GAP-01 GAP-01_"

gh issue comment "$ISSUE_NUMBER" --body "$CLAIM_COMMENT" 2>&1 | sed 's/^/  /' || true

# ─── STEP 5: AUTO-SYNC WORKSPACE (Zero Drift Protection) ─────────────────
echo "🔄 Auto-syncing workspace with latest origin/main..."
python3 scripts/git/auto_sync_main.py 2>/dev/null || python scripts/git/auto_sync_main.py 2>/dev/null || true

echo "✅ Atomic claim successful — issue #$ISSUE_NUMBER owned by $AGENT_NAME"
exit 0
