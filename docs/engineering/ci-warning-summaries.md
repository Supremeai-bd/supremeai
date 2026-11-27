# CI annotation summaries

`Warning Annotation Summary` runs after the named workflows complete, using only
read permissions and code from the default branch. It reports warning/failure
annotation counts by source job, links each affected check, and checks CodeQL
results for the same SHA. Matrix jobs and run attempts are queried separately.
It is a reporting workflow: it does not change the original check conclusion,
approve a PR, or bypass any gate. Once merged, GitHub must register the workflow
on the default branch before `workflow_run` reporting can begin.

The reporter **does not capture arbitrary log lines** (including compiler and
linter output which was never made an annotation), repository-wide security
alerts, Dependabot, other SHAs, or checks not accessible to its token. CodeQL
checks for the same SHA may not belong to the exact triggering run; they can
also appear or change after this snapshot. Skipped/cancelled jobs did not run.
API, pagination, permission or checkout failures mean the report is incomplete,
not that there are no warnings. Inspect the original run on failure. Annotations
are linked rather than copied because messages and paths can contain sensitive
or attacker-controlled content. Review the original check for each message.

The weekly CodeQL workflow restores scheduled coverage; it uses GitHub-hosted
runner time. The reporter also uses runner time after each watched run. Neither
workflow creates a production service, but free CI minutes or zero total cost
are **not** guaranteed; monitor account usage and quotas.

High-risk PR semantic verification is fail-closed when evidence, a valid model
verdict, or a reviewer are unavailable. External diff transmission is disabled
by default; opting in requires a reviewed privacy and cost policy and does not
make an LLM verdict proof of safety. Regex matches are not semantic review.
Large diffs and API evidence failures require human attention. Existing branch
protection and required checks remain in effect.
