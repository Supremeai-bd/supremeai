#!/bin/sh
# SupremeAI shared pre-push hook (committed; install via: python scripts/setup_git_hooks.py)
# 1. Block if behind origin/main (prevents stale-PR conflicts)
git fetch origin main --quiet 2>/dev/null || true
behind=$(git rev-list --count HEAD..origin/main 2>/dev/null || echo 0)
if [ "$behind" -gt 0 ]; then
    echo "" >&2
    echo "Your branch is $behind commit(s) behind origin/main." >&2
    echo "Rebase before pushing: git fetch origin main && git rebase origin/main" >&2
    echo "" >&2
    exit 1
fi
# 2. Zero-regression gate
python scripts/pre_push_hook.py 2>/dev/null || true
exit 0
