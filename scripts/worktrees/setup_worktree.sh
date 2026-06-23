#!/bin/bash
# ============================================================================
# script >> setup_worktree.sh
# project >> SupremeAI 2.0
# purpose >> General utility
# module >> scripts
# ============================================================================
    if [ -d "$worktree_path" ]; then
        echo "Worktree already exists at $worktree_path"
        exit 1
    fi

    echo "Creating worktree for task: $task_name"
    git worktree add "$worktree_path" -b "agent/$task_name" "$branch_name"

    echo "Worktree created at: $worktree_path"
    echo "Branch: agent/$task_name"
}

list_worktrees() {
    echo "Active worktrees:"
    git worktree list
}

remove_worktree() {
    local task_name="$1"
    local worktree_path="$WORKTREES_DIR/$task_name"

    if [ ! -d "$worktree_path" ]; then
        echo "Worktree not found at $worktree_path"
        exit 1
    fi

    git worktree remove "$worktree_path"
    git branch -d "agent/$task_name" 2>/dev/null || true
    echo "Worktree removed: $task_name"
}

case "${1:-}" in
    create)
        create_worktree "${2:-}" "${3:-}"
        ;;
    list)
        list_worktrees
        ;;
    remove)
        remove_worktree "${2:-}"
        ;;
    *)
        echo "Usage: $0 {create|list|remove} [args...]"
        exit 1
        ;;
esac
