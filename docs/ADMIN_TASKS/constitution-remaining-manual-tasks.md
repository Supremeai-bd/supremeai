# Constitution implementation — manual tasks

The automated foundation and governance checks are in place. These items require an authorized owner or live provider access and are intentionally not performed by CI:

- Approve the transition from advisory to blocking mode, with a reviewed CI run URL and false-positive decision.
- Assign owners and expiry dates for every real exemption; never merge a permanent exemption.
- Review protected paths and CODEOWNERS for constitution/rules, deployment, auth, billing, and tenant boundaries.
- Connect the organization notification destination (Slack/email) and define escalation ownership.
- Configure durable storage for CI summaries and expose it through the existing CI dashboard API; the current in-memory API is not production persistence.
- Run a production-like backup restore drill and attach evidence to the release record.
- Approve retention/privacy policy for audit artifacts and set repository artifact retention accordingly.
- Review new detector baselines and promote only after human false-positive/negative review.
- Obtain security approval before enabling any autonomous remediation or deployment mutation.

Use `scripts/ci/build_manual_task_report.py` to generate a non-secret checklist report. These tasks must not be marked complete from repository-local evidence alone.
