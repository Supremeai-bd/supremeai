#!/bin/bash
# ============================================================================
# script >> setup_test_env.sh
# project >> SupremeAI 2.0
# purpose >> Unit testing and QC
# module >> scripts
# ============================================================================
case "${1:-}" in
    create)
        create_test_env
        ;;
    destroy)
        destroy_test_env
        ;;
    *)
        echo "Usage: $0 {create|destroy}"
        exit 1
        ;;
esac
