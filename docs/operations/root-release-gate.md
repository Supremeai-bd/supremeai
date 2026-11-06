# Root release gate

The root release gate is open only when all of the following are true:

1. Every configured service has a valid canonical mapping.
2. Provider reachability and application/worker HTTP health are both passing.
3. Intended GitHub SHA, deployed SHA, and runtime `/release` SHA are equal.
4. Supabase project reference, expected tables, and migration version are explicitly verified.
5. Cloudflare worker route returns the expected success response; a provider-level 404 is a failure.
6. The AST graph is indexed and is not empty.
7. The parity audit returns `verified`, not merely `configuration_present` or `unverified`.

`unknown`, `unverified`, `unavailable`, and `configuration_present` are blocking
states for production sign-off. They may be acceptable for read-only monitoring,
but must never be converted to `healthy` by an aggregate status function.

