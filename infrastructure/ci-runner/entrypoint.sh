#!/bin/bash
set -e

GH_REPO="${GH_REPO:-Supremeai-bd/supremeai}"
RUNNER_NAME="${RUNNER_NAME:-supremeai-kiri-runner}"
RUNNER_LABELS="${RUNNER_LABELS:-self-hosted,local-pc,kiri,linux}"

if [ -z "${RUNNER_TOKEN}" ]; then
    echo "ERROR: RUNNER_TOKEN is required to register the self-hosted runner."
    echo "Generate one using: gh api repos/${GH_REPO}/actions/runners/registration-token -X POST"
    exit 1
fi

cleanup() {
    echo "Stopping runner and unregistering..."
    if [ -n "${REMOVE_TOKEN}" ]; then
        ./config.sh remove --token "${REMOVE_TOKEN}" || true
    fi
}

trap 'cleanup; exit 130' INT
trap 'cleanup; exit 143' TERM

if [ ! -f .runner ]; then
    echo "Configuring GitHub Actions Runner for ${GH_REPO}..."
    ./config.sh \
        --url "https://github.com/${GH_REPO}" \
        --token "${RUNNER_TOKEN}" \
        --name "${RUNNER_NAME}" \
        --labels "${RUNNER_LABELS}" \
        --work "_work" \
        --unattended \
        --replace
fi

echo "Starting GitHub Actions Runner (${RUNNER_NAME})..."
./run.sh &
RUN_PID=$!

wait $RUN_PID
