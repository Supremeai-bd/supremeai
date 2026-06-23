#!/bin/bash
# ============================================================================
# script >> run_task.sh
# project >> SupremeAI 2.0
# purpose >> Task routing
# module >> scripts
# ============================================================================
        echo "Error: Worktree not found for task '$task_name'. Run setup_worktree.sh create first."
        exit 1
    fi

    echo "Running task '$task_name' in $worktree_path"
    cd "$worktree_path"
    
    if [ -f "pyproject.toml" ]; then
        poetry run $command
    elif [ -f "package.json" ]; then
        pnpm run $command
    else
        eval "$command"
    fi
}

run_task "${1:-}" "${2:-pytest}"
