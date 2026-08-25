#!/usr/bin/env bash
# R12 FIX — Move top-level test_*.py files into their module subfolders.
#
# The `backend/tests/` directory had ~40 test files dumped at the top level
# instead of being grouped by module. This script moves them into their
# proper subfolders (core/, agents/, api/, etc.) using `git mv` so history
# is preserved.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)/backend/tests"

MOVED=0

move_to() {
    local target_dir="$1"
    local pattern="$2"
    [ -d "$target_dir" ] || return 0
    for f in $pattern; do
        [ -e "$f" ] || continue
        if [ "$f" != "$target_dir/$(basename "$f")" ]; then
            git mv "$f" "$target_dir/$f" 2>/dev/null && MOVED=$((MOVED+1)) || true
        fi
    done
}

move_to "core"    "test_core_*.py"
move_to "agents"  "test_agents_*.py"
move_to "api"     "test_api_*.py"
move_to "api"     "test_ephemeral_*.py"
move_to "api"     "test_e2e_*.py"
move_to "api"     "test_*_router.py"
move_to "tools"   "test_tools_*.py"
move_to "services" "test_services_*.py"
move_to "engine"  "test_engine_*.py"
move_to "brain"   "test_brain_*.py"
move_to "workers" "test_workers_*.py"
move_to "evolution" "test_evolution_*.py"
move_to "monitoring" "test_monitoring_*.py"
move_to "security" "test_security_*.py"
move_to "middleware" "test_middleware_*.py"
move_to "runtime"  "test_runtime_*.py"
move_to "learning" "test_learning_*.py"
move_to "orchestration" "test_orchestration_*.py"

echo "✅ R12: Moved $MOVED test files into proper subfolders."
echo "Run 'git status' to review. Commit with: 'chore(tests): R12 organize test files'"
