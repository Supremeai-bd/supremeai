# Landing decisions and their limits

The trusted-base `tiny_brain_pr_guard.py` is the existing landing authority; this
change does not add a merge path, bypass checks, or create a review override.
The following describes the **proposed candidate policy**. It takes effect only
after an independently reviewed version reaches the trusted base.

* **BLOCKED**: required run-scoped CI is not successful, candidate identity or
  tested merge/base/head is stale or unavailable, the PR is a draft/fork/closed,
  or the changed-file list is incomplete or malformed. Missing evidence is not
  proof of a malicious change; it still cannot safely land. A failed upstream
  semantic verifier also prevents reaching this decision job.
* **OWNER_REVIEW**: complete successful CI plus protected authentication,
  security, source discovery, memory, agent/tool policy, production, workflow,
  and selected gate-test changes; an unverified bridge submitter; or an unknown
  file surface. Both old and new names of renames are checked. Review never
  overrides failed checks. Review is an actual stop only if the GitHub
  `production-approval` environment has effective required reviewers and main
  has appropriate rules; the workflow's environment declaration alone is not
  evidence of that configuration.
* **AUTO_MERGE candidate**: all required current-candidate evidence succeeds,
  the bridge submitter rule passes, and every path is within explicitly scoped
  documentation/Python tests or existing service/API categories, excluding
  protected files. The existing optional advisor may only downgrade this result.
  No canary soak is enforced by this classifier. Required GitHub branch rules
  must also pass.

Classification is based on filenames, not a verified semantic understanding of
code, test removal, secrets or malicious instructions. Protected paths are an
incomplete inventory, tests and docs can themselves cause harm, and unlisted
sensitive service files may still fall into the existing auto-merge scope. The
semantic verifier and CI are additional gates, not proof of safety. Do not call
this a guarantee of safe automatic merge. Bridge label authority, environment
settings, branch rules, and mutable labels between decision and merge require
independent verification; the candidate-only final recheck does not reclassify
labels. An optional advisor's absence does not block the existing path.

The trusted-base semantic verifier currently rejects oversized PR diffs without a
review override. A proposed verifier/guard change cannot validate itself; use a
separately reviewed trusted-base policy or authorized decomposition, not an
unreviewed bootstrap, diff truncation, or protection bypass. This policy adds no
production service or model call; GitHub CI usage may still incur charges.
