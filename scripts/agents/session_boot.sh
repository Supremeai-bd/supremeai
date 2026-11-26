# =============================================================================
# scripts/agents/session_boot.sh — Session Bootstrap, এক কমান্ডে (Audit A1)
#
# AGENTS.md-এর Bootstrap Checklist-এর ৭টা manual ধাপকে এক কমান্ডে orchestrate করে:
#   1. git fetch --prune
#   2. AGENTS.md (generated SSOT) digest — পরিবর্তন হলে প্রথম ২০ লাইন দেখায়
#   3. PR_TO_PRODUCTION_LIFECYCLE digest (আছে হলে)
#   4. acquire_role_slot.py --lane <role> [--issue N]  (slot + branch)
#   5. atomic_claim.sh <issue#> <agent>  (claim + 'Touching files' ঘোষণার রিমাইন্ডার)
#   6. mcp_tower_client.py heartbeat  (Control Tower-এ state=online)
#   7. 3-Tier Verification রিমাইন্ডার (Reflection → Boot smoke → Pytest)
#
# Regression-safe: কোনো gate bypass নয় — প্রতিটি পুরনো স্ক্রিপ্টকে সেই ক্রমেই call
# করে; কোনো ধাপ fail করলে exit code সহ থামে (set -e)। Bash-only (GitHub/WSL/CI),
# Windows-এ Git Bash থেকে চালানো যাবে।
#
# Usage:
#   ./scripts/agents/session_boot.sh --lane coder            # অটো-ডিসকভারি
#   ./scripts/agents/session_boot.sh --lane coder --issue 630
#   ./scripts/agents/session_boot.sh --lane coder --issue 630 --no-claim --dry-run
# =============================================================================
set -euo pipefail

LANE=""
ISSUE=""
AGENT_NAME="agent-$(date +%s)"
DRY_RUN=0
NO_CLAIM=0

# বাংলা মন্তব্য: flag পার্স — কোনো side-effect নেই, শুধু ভ্যালু জমা
while [[ $# -gt 0 ]]; do
  case "$1" in
    --lane) LANE="$2"; shift 2 ;;
    --issue) ISSUE="$2"; shift 2 ;;
    --agent) AGENT_NAME="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --no-claim) NO_CLAIM=1; shift ;;
    -h|--help)
      grep '^#' "$0" | sed -n '1,40p'; exit 0 ;;
    *) echo "Unknown flag: $1"; exit 2 ;;
  esac
done

if [[ -z "$LANE" ]]; then
  echo "Usage: $0 --lane <auditor|coder|planner|platform|browser> [--issue N] [--agent ID] [--dry-run]" >&2
  exit 2
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

step() { printf '\n\033[1;36m== [%s] %s\033[0m\n' "$(date +%H:%M:%S)" "$1"; }
run()  { if [[ $DRY_RUN -eq 1 ]]; then echo "(dry-run) $*"; else "$@"; fi }

step "1/6 git fetch --prune (main sync)"
run git fetch origin --prune
CURRENT_BRANCH="$(git branch --show-current 2>/dev/null || echo '')"
if [[ "$CURRENT_BRANCH" != "main" ]]; then
  echo "Note: current branch is '$CURRENT_BRANCH' (not main). Main-এ সাঁটলে fetch+pull করো।"
  if [[ "$CURRENT_BRANCH" == "main" || -z "$CURRENT_BRANCH" ]]; then
    run git pull --ff-only origin main
  fi
else
  run git pull --ff-only origin main
fi

step "2/6 AGENTS.md digest (rules পরিবর্তন হয়েছে কিনা)"
if [[ -f AGENTS.md ]]; then
  echo "AGENTS.md (SSOT: .github/constitution/rules.yml) — প্রথম শিরোনাম:"
  sed -n '1,6p' AGENTS.md
  echo "…(বিস্তারিত নিজে পড়ো — cat AGENTS.md)"
else
  echo "WARNING: AGENTS.md missing — generate করো: python scripts/ci/generate_agents_md.py"
fi

step "3/6 PR lifecycle digest"
if [[ -f docs/PR_TO_PRODUCTION_LIFECYCLE.md ]]; then
  echo "docs/PR_TO_PRODUCTION_LIFECYCLE.md আছে — session-এ প্রথমবার পড়ো (cat docs/PR_TO_PRODUCTION_LIFECYCLE.md)"
else
  echo "docs/PR_TO_PRODUCTION_LIFECYCLE.md নেই — skip"
fi

step "4/6 acquire_role_slot --lane $LANE ${ISSUE:+--issue $ISSUE}"
SLOT_ARGS=(--role "$LANE")
if [[ -n "$ISSUE" ]]; then SLOT_ARGS+=(--issue "$ISSUE"); fi
run python scripts/agents/acquire_role_slot.py "${SLOT_ARGS[@]}"

# বাংলা মন্তব্য: acquire_role_slot যে branch বানায় সেটা এখন current
BRANCH="$(git branch --show-current 2>/dev/null || echo '')"
echo "Active branch: ${BRANCH:-<unknown>}"

step "5/6 atomic claim ${ISSUE:+for issue #$ISSUE}"
if [[ $NO_CLAIM -eq 1 ]]; then
  echo "(--no-claim) claim step skipped — কোডের আগে claim মনে রেখো (No Claim, No Code)"
elif [[ -z "$ISSUE" ]]; then
  echo "Issue নির্দিষ্ট নেই — acquire_role_slot যে issue বেছেছে সেটার claim নিজে চালাও:"
  echo "  ./scripts/ci/atomic_claim.sh <issue#> <slot-id>"
else
  SLOT_ID="${BRANCH%%-*}-$(echo "$BRANCH" | cut -d- -f2- | cut -d- -f1)"
  echo "Claim command: ./scripts/ci/atomic_claim.sh $ISSUE $SLOT_ID"
  run ./scripts/ci/atomic_claim.sh "$ISSUE" "$SLOT_ID"
  echo "Reminder: claim comment-এ 'Touching files: file1, file2' ঘোষণা করো।"
fi

step "6/6 MCP Tower heartbeat ($AGENT_NAME)"
if [[ -f scripts/agents/mcp_tower_client.py ]]; then
  run python scripts/agents/mcp_tower_client.py heartbeat --slot "agent-$(echo "$AGENT_NAME" | tail -c 6)" --name "$AGENT_NAME" || \
    echo "(heartbeat fail = non-blocking; tower offline হতে পারে)"
fi

step "Bootstrap শেষ — 3-Tier Verification মনে রাখো"
cat <<'EOF'
  1) Reflection check (grep — কী বদলালাম তা নিজেই যাচাই)
  2) Boot smoke test (python -c 'import main' / py_compile)
  3) Pytest (targeted, তারপর ব্রড)
  টেস্ট ম্যানিপুলেশন (delete/skip/fake) কঠোর নিষিদ্ধ।
EOF

echo ""
echo "✅ session boot complete — lane=$LANE issue=${ISSUE:-auto} branch=$BRANCH"
