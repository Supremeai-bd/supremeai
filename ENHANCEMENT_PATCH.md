# SupremeAI Smart CI — Enhancement Patch Guide
# Apply these changes to your existing .github/workflows/supreme-ci.yml

## CHANGE 1: Add workflow_dispatch inputs at the top (after existing inputs)

Add these inputs to the `workflow_dispatch` block:

```yaml
workflow_dispatch:
  inputs:
    # ... existing inputs ...
    forced_jobs:
      description: 'JSON array of job IDs to force-run regardless of path detection (used by auto-fix re-trigger)'
      required: false
      default: '[]'
      type: string
    is_retry:
      description: 'Whether this run is an auto-fix retry'
      required: false
      default: 'false'
      type: choice
      options:
        - 'false'
        - 'true'
```

## CHANGE 2: Replace the entire `check-previous-failures` job with the Python script

Replace the entire `check-previous-failures` job (JOB 1.5) with:

```yaml
  check-previous-failures:
    name: 🤔 Check Previous Failures
    runs-on: ubuntu-latest
    outputs:
      force_flags: ${{ steps.check.outputs.force_flags }}
    steps:
      - uses: actions/checkout@v7
        with:
          fetch-depth: 1

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'

      - name: Detect previous failures & skips
        id: check
        env:
          GH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          GITHUB_REPOSITORY: ${{ github.repository }}
          GITHUB_REF_NAME: ${{ github.ref_name }}
          GITHUB_RUN_ID: ${{ github.run_id }}
          WORKFLOW_NAME: "SupremeAI Smart CI"
        run: |
          pip install requests
          python .github/scripts/detect-previous-failures.py
```

## CHANGE 3: Enhance `combine-decisions` to handle forced_jobs from dispatch

In the `combine-decisions` job (JOB 1.6), add after the `force` step:

```yaml
      - name: Read forced jobs from retry dispatch
        id: retry
        run: |
          FORCED='${{ github.event.inputs.forced_jobs }}'
          if [ -z "$FORCED" ] || [ "$FORCED" = "[]" ]; then
            echo "forced_jobs={}" >> $GITHUB_OUTPUT
          else
            echo "forced_jobs=$FORCED" >> $GITHUB_OUTPUT
          fi
          echo "is_retry=${{ github.event.inputs.is_retry || 'false' }}" >> $GITHUB_OUTPUT
```

Then modify the `decide` function in the `combine` step to also check forced_jobs:

```bash
          decide() {
            local pkg="$1"
            local changed="$2"
            local forced="$3"
            local workflow_changed="${{ needs.detect-changes.outputs.workflow }}"
            local monorepo_changed="${{ needs.detect-changes.outputs.monorepo_config }}"
            local is_retry="${{ steps.retry.outputs.is_retry }}"
            local forced_jobs='${{ steps.retry.outputs.forced_jobs }}'

            # Check if this package is in the forced_jobs list
            local in_forced_list="false"
            if echo "$forced_jobs" | jq -e ". | contains([\"${pkg}\"])" >/dev/null 2>&1; then
              in_forced_list="true"
            fi
            # Also check by full job name patterns
            if echo "$forced_jobs" | jq -e ". | map(ascii_downcase) | contains([\"${pkg}-test\"]) or contains([\"${pkg}-build\"]) or contains([\"${pkg}-analyze\"])" >/dev/null 2>&1; then
              in_forced_list="true"
            fi

            if [ "$changed" = "true" ] || [ "$forced" = "true" ] || [ "$workflow_changed" = "true" ] || [ "$monorepo_changed" = "true" ] || [ "$in_forced_list" = "true" ]; then
              echo "${pkg}_run=true" >> $GITHUB_OUTPUT
              echo "${pkg}=true" >> $GITHUB_OUTPUT
              echo " ✅ ${pkg}: WILL RUN (changed=$changed, forced=$forced, retry=$is_retry, in_forced_list=$in_forced_list)"
            else
              echo "${pkg}_run=false" >> $GITHUB_OUTPUT
              echo "${pkg}=false" >> $GITHUB_OUTPUT
              echo " ⏭️ ${pkg}: SKIPPED"
            fi
          }
```

## CHANGE 4: Add explicit retry detection to job conditions

For each test/build job (backend-test, studio-build, etc.), add `if: always()` to the final status steps and ensure the main `if` condition also respects retry:

Example for `backend-test`:
```yaml
  backend-test:
    name: 🐍 Backend Tests
    runs-on: ubuntu-latest
    needs: [detect-changes, combine-decisions]
    timeout-minutes: 15
    if: |
      needs.combine-decisions.outputs.backend_run == 'true' || 
      contains(fromJson(github.event.inputs.forced_jobs || '[]'), 'backend-test') ||
      contains(fromJson(github.event.inputs.forced_jobs || '[]'), 'backend_test') ||
      contains(fromJson(github.event.inputs.forced_jobs || '[]'), '🐍 Backend Tests')
    continue-on-error: true
```

Repeat similar for studio-build, mobile-analyze, webchat-build, vscode-build, prompt-eval.

## CHANGE 5: Improve artifact retention for failure flags

In the `ci-report` job, add a step to download previous failure flags before generating report:

```yaml
      - name: Download previous failure flags
        uses: actions/download-artifact@v7
        with:
          name: ci-failure-flags
          path: .ci-status-prev
        continue-on-error: true
```

This helps the next run detect failures even if the GitHub API is rate-limited.

## CHANGE 6: Add a `skipped-jobs-recorder` step in ci-report

In the `ci-report` job, after generating the report, also output which jobs were skipped:

```yaml
      - name: Record skipped jobs
        if: always()
        run: |
          SKIPPED_JOBS=$(jq -n '[${{ toJson(needs) }} | to_entries[] | select(.value.result == "skipped") | .key]')
          echo "skipped_jobs=$SKIPPED_JOBS" >> $GITHUB_OUTPUT
          echo "Skipped jobs: $SKIPPED_JOBS"
```

## CHANGE 7: Add `workflow_run` trigger for auto-fix (optional, if you want auto-fix on every failure)

Actually, the auto-fix workflow already handles this via `workflow_run` event. No change needed in supreme-ci.yml.

## CHANGE 8: Ensure `ci-report` artifact is always uploaded even on early failure

The current `ci-report` job already has `if: always()` and uploads the artifact. Make sure the artifact name is consistent:

```yaml
      - name: Upload CI Report Artifact
        if: always()
        uses: actions/upload-artifact@v5
        with:
          name: ci-report
          path: failure-report.md
          retention-days: 7  # Increase from 3 to 7 for auto-fix window
```
