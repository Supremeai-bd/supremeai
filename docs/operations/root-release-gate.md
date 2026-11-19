# Root release gate

The root release gate is open only when all of the following are true:

1. Every configured service has a valid canonical mapping.
2. Provider reachability and application/worker HTTP health are both passing.
3. The exact triggered Render deployment is `live`; its commit and the HTTPS
   runtime `/release` commit both match the full intended GitHub SHA.
4. Supabase project reference, expected tables, and migration version are explicitly verified.
5. Cloudflare worker route returns the expected success response; a provider-level 404 is a failure.
6. The AST graph is indexed and is not empty.
7. The parity audit returns `verified`, not merely `configuration_present` or `unverified`.

`unknown`, `unverified`, `unavailable`, and `configuration_present` are blocking
states for production sign-off. `not_run` (e.g. a suspended auxiliary CI runner)
and `metadata_only` are not runtime evidence. They may be acceptable for read-only monitoring,
but must never be converted to `healthy` by an aggregate status function.

Record the operator decisions and external evidence in the
[manual rollout checklist](manual-rollout-checklist.md).
