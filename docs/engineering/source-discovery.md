# Consent-based source discovery (preview, default off)

This is a **source discovery**, not an autonomous research or verified-answer feature.
The server searches one fixed public provider per request: Bing News RSS (`news`),
Crossref (`research`), English Wikipedia (`reference`), or GitHub repositories
(`technical`). `auto` uses conservative keyword rules and asks for clarification
when they are ambiguous or a timely fact lacks an appropriate source. These are
only candidate sources: there is no article fetch, claim verification, synthesis,
exhaustive coverage, weather or price provider. Results and excerpts are untrusted
external text. Links are displayed, not fetched by the server. Availability,
publisher links, licensing, accuracy, currency and operating cost are not verified.

## Operational gates

* Deploy both Core and Gateway. Core already declares `httpx`, `defusedxml` and
  Redis dependencies. The Gateway proxies to `CORE_API_URL`; it does not import
  Core or make external provider requests itself.
* The Core environment flag `SUPREMEAI_SOURCE_DISCOVERY=true` is required. It is
  **off** otherwise. Use the authenticated tenant's `crawl_policies` row: active,
  and authorizing the selected hostname by `allowed_domains` or an explicit
  domain rule (`www.bing.com`, `api.crossref.org`,
  `en.wikipedia.org`, `api.github.com`). The authenticated token must include
  a nonempty `tenant_id` or `org_id`; the personal subject is not a tenant fallback. Policies come only from the authoritative
  database; no in-memory fallback. DNS safety checks apply. Failure is closed.
* A working Redis instance is required; an atomic, Redis-clock domain-wide limit
  is the lower of the policy RPM and 10 requests/minute. The concurrency limit is
  eight per Core process, not fleet-wide. No quota fallback. This protects the
  shared provider, but does not replace per-tenant/user abuse controls.
* Only a public API endpoint is fetched, with no redirects, no environment proxy,
  identity content encoding, a 10-second total HTTP deadline, and a 256 KB cap.
  Restrictions may make some providers unavailable. API terms, robots obligations
  and permitted usage must be reviewed before enabling; the crawl policy does
  **not** enforce expiry or perform a live robots.txt check. Fixed hosts reduce but do not eliminate DNS
  rebinding risk because the DNS precheck and connection are separate resolutions.
* An explicit `consent: true` is required on each call. The query is sent to the
  named third party and may be retained by it; do not include personal data or
  secrets. HTTPX request-status log messages for this task are redacted; broader
  infrastructure/proxy/provider logging is outside that guarantee. Chat messages,
  result text and cited links can enter the existing owner-scoped conversation
  storage if a conversation ID is supplied. This feature does not grant long-term
  memory consent. Existing retention and deletion rules apply.

## API flow

Authenticated `POST /api/v1/research/source-search` (alias
`/v1/research/source-search`):

```json
{"query":"dengue vaccine research","kind":"auto","consent":false}
```

`consent: false` returns a plan/notice without outbound search; if ambiguous,
select a `kind` and ask again. After the user approves the exact query and named
provider, send the same request with boolean `consent: true`. HTTP errors remain
errors, not invented results. The dedicated endpoint returns a bounded list of
`title`, `url`, `publisher`, `published` and `snippet` where available.

For an explicit chat completion, add `source_search` to the ordinary chat body:

```json
{"model":"supreme-spark","messages":[{"role":"user","content":"ডেঙ্গুর গবেষণাপত্র খুঁজে দাও"}],"source_search":{"query":"dengue vaccine","kind":"research","consent":true},"stream":false}
```

The chat response renders source titles, excerpts, links and a clear verification
limitation; the model is not called for that turn. Streaming emits the same result
as an SSE completion after the search finishes. **Ordinary chat does not yet infer
or attach this field.** A client must implement the consent/clarification flow;
no existing UI has been integrated. Do not automatically set `consent: true`
from chat text or a model-generated instruction. A preliminary plan can change if
the query/kind changes; get consent for the actual sent query and source. The
upstream API can omit abstracts or return no usable HTTPS links.

Offline tests cover mocked Core/Gateway/network wiring and failure paths; they do
not prove real Redis, production policy data, provider behavior, deployment or
UI-to-chat completion. Enabling requires separate operational review and live
validation with authorization, including concurrency and tenant isolation.
