# SupremeAI: নিরাপদ শেখা, মানুষ বোঝা ও শূন্য-অতিরিক্ত-খরচ পরিকল্পনা

**অবস্থা: পরিকল্পনা ও আংশিক local implementation; অনুমোদিত rollout নয়।** এই পরিকল্পনা model training, production privacy বা zero spend ইতিমধ্যে সম্পন্ন হয়েছে বলে দাবি করে না। বাস্তব deployment, billing, quota এবং provider terms স্বাধীনভাবে যাচাই করতে হবে। কাজের রেফারেন্স: #909; আগের আংশিক সংশোধন #912।

## 1. লক্ষ্য ও শব্দের অর্থ

প্রাধান্য: (১) ব্যক্তিগত তথ্য ও নিরাপত্তা, (২) সত্যতা ও পরিমাপযোগ্য quality, (৩) ছোট ও নিয়ন্ত্রিত latency, (৪) **অতিরিক্ত নগদ খরচের লক্ষ্য $0**। খরচ অস্পষ্ট হলে বা অনুমোদিত free quota শেষ হলে fail closed / পরিষ্কার unavailable; গোপনে paid fallback নয়। Free tier পরিবর্তন হতে পারে; বিদ্যুৎ, hardware, কর্মঘণ্টা ও সুযোগ-খরচ প্রকৃত অর্থনৈতিক খরচ হলেও cloud bill-এ শূন্য হতে পারে। 24/7 availability বা অনির্দিষ্ট user scale এবং কঠোর $0 একসাথে নিশ্চিত করা যায় না। Provider-এর বৈধ ব্যবহার, শর্ত ও সীমা মানতে হবে; quota এড়াতে account/session ঘোরানো নয়।

- **Model training / fine-tuning:** model weights পরিবর্তন; compute, data rights ও validation লাগে।
- **Inference-time improvement:** ওজন না বদলে যাচাই করা নির্দেশনা, উদাহরণ, retrieval এবং user-approved preference যুক্ত করা। কিছু ক্ষেত্রে fine-tuning-এর কম-খরচের বিকল্প, কিন্তু সাধারণ দক্ষতা, latency বা সব task-এ সমতুল্য নয়; prompt token খরচ বাড়তে পারে।
- **Decision evidence:** কাজের সংক্ষিপ্ত প্রেক্ষাপট, বেছে নেওয়া পথ, পরীক্ষিত প্রমাণ, সীমাবদ্ধতা ও বিকল্প। এটি model-এর গোপন chain-of-thought নয় এবং AI-এর নিজের ব্যাখ্যাকে প্রকৃত অন্তর্নিহিত চিন্তার faithful transcript ধরা যায় না। আসল ফল ও স্বাধীন test বেশি শক্ত প্রমাণ।

## 2. বর্তমান কোডে কী আছে, কী নেই

- `gateway/service/context_compiler.py`: identity anchor, scoped context ও memory আছে; #912 অনিরীক্ষিত collective knowledge chat prompt থেকে সরিয়েছে। Summary, durable memory, client-provided preference এবং অন্যান্য routes-এর trust boundary এখনও সম্পূর্ণ নয়।
- `gateway/service/user_memory_engine.py`: preference extraction/cloud sync আছে; এটি সম্মতি, provenance, delete propagation ও verification-সহ একটি পূর্ণ learning pipeline নয়। বিদ্যমান ব্যক্তিগত তথ্যকে প্রশিক্ষণ বা shared knowledge হিসেবে ব্যবহার করার অনুমতি অনুমান করা যাবে না।
- `scripts/ci/ai_knowledge_exchange.py` ও `scripts/ci/ingest_pr_knowledge.py`: issue/PR/manual input থেকে knowledge নেয়; `active` বা regex validation তথ্যকে সত্য বা বিশ্বস্ত source প্রমাণ করে না। পুরোনো ingestion path এখনও স্বয়ংক্রিয়ভাবে quarantine enforcement করে না; সেটিকে নিরাপদ ঘোষণা করা যাবে না।
- `scripts/ci/decision_records.py`: GitHub issue/PR body ও comments থেকে `ai-decision-record/1`-এ থাকা সীমিত vocabulary-র `reasoning_pattern` সংগ্রহ করে। `python scripts/ci/decision_records.py --catalog` ও `python scripts/ci/decision_records.py --issue 909 --repo Supremeai-bd/supremeai` দিয়ে local read-only review সম্ভব। Output-এ task-specific prose/answer নয়, issue/comment author ও revision metadata-সহ quarantined pattern থাকে। এটি approval, সত্যতা বা PII-নিরাপত্তা প্রমাণ করে না, Supabase-এ লেখে না এবং runtime-এ প্যাটার্ন ঢোকায় না। পুরোনো record-এ pattern না থাকলে সেটি বাদ যায়; free-text থেকে উদ্দেশ্য অনুমান করা হয় না।
- `gateway/service/free_route_policy.py`: নির্দিষ্ট API route-এর approval ও expiry আছে, কিন্তু সব inference, relay, hosting, storage, egress ও operational billing-এর জন্য শেষ-থেকে-শেষ zero-spend প্রমাণ নয়। `scripts/ops/redis_quota_monitor.py` ব্যবহারের estimate হতে পারে, সর্বত্র billing truth নয়।
- `evals/golden/run_eval.py`: fixture-based test evaluator-এর mechanics যাচাই করে, live model quality নয়।
- #912 merge হয়েছে; deployed SHA, বাস্তব traffic, provider price/quota ও Supabase persistence এখানে যাচাই করা হয়নি।

## 3. Architecture: পৃথক চারটি স্তর

1. **Private user preference:** একক verified principal, explicit opt-in, দেখার/সংশোধনের/মুছে ফেলার অধিকার, expiry এবং ব্যক্তিগত scope। অন্য user বা training pool-এ রপ্তানি নয়।
2. **Decision candidate inbox:** Issue/PR থেকে ঘোষিত marked JSON, trusted platform থেকে নেওয়া প্রকৃত source actor ও immutable reference; packet-এর নিজের `agent`/`source` claim আলাদাভাবে untrusted। Schema ও size limit যাচাই; secret/PII scan হলো defense-in-depth, সম্পূর্ণ privacy proof নয়। অবৈধ হলে quarantine বা reject।
3. **Reviewed knowledge:** স্বাধীন reviewer, source/evidence যাচাই, outcome ও applicable scope উল্লেখ; approval ও তার revision audit trail। শুধুমাত্র approved version query করা যাবে। User content বা retrieved data কখনও system instruction হিসেবে বিশ্বাস করা যাবে না; model output দিয়েও policy পরিবর্তন নয়। উচ্চ ঝুঁকির ক্ষেত্রে মানব সিদ্ধান্ত আবশ্যক।
4. **Evaluation dataset:** স্পষ্ট আলাদা opt-in, provenance, consent/version, licence, minimization, retention এবং reviewer approval সহ sanitised examples; training purpose আলাদা। Withdraw/delete হলে derived copies/index/datasets থেকে অপসারণ ও audit, সম্ভব না হলে deletion limitation আগেই জানাতে হবে। কোনো স্বয়ংক্রিয় model-weight update নয়।

### Decision record (ব্যবহারযোগ্য সংক্ষিপ্ত উদাহরণ)

```json
{
  "schema": "ai-decision-record/1",
  "agent": "review-agent",
  "task_type": "bugfix",
  "task_ref": "issue-909",
  "decision": "Reject stateful requests without a verified identity",
  "reason": "A shared anonymous principal cannot isolate user data",
  "alternatives_rejected": ["Store every anonymous user under one ID"],
  "evidence": ["local owner-isolation regression test"],
  "verification": [{"check": "local regression", "result": "passed"}],
  "limitations": ["deployment and client migration not verified"],
  "status": "tested",
  "reasoning_pattern": {
    "task_family": "safety",
    "steps": ["clarify_goal", "inspect_evidence", "check_risks", "verify_outcome", "state_limitations"],
    "checks": ["user_constraints", "reproducible_test", "privacy"],
    "stop_conditions": ["missing_evidence", "requires_human_review"]
  }
}
```

এটি কোনো নির্দেশনার উৎস নয়; প্রমাণ যাচাই না হওয়া পর্যন্ত quarantine-এ থাকবে। ভবিষ্যৎ schema-তে server-recorded source, immutable revision, test provenance, reviewer, expiry, consent এবং revocation যোগ করে versioning করতে হবে। Record, execution result এবং reviewer verdict আলাদা রাখতে হবে। Secret, raw conversation, confidential vulnerability বা ব্যক্তিগত তথ্য public issue/PR-এ লেখা নিষেধ।

## 4. মানুষের প্রয়োজন বোঝা: আচরণ নয়, সম্মত preference

- প্রশ্নের ভাষা (বাংলা/English/Banglish), কাঙ্ক্ষিত সংক্ষিপ্ততা, কাজের লক্ষ্য ও ব্যবহারকারী প্রকাশ্যে বলা constraint বর্তমান কথোপকথনে সম্মান করো। ভাষা থেকে জাতি, ধর্ম, লিঙ্গ, বয়স, মানসিক অবস্থা, বিশ্বাস বা personality অনুমান নয়। সন্দেহ হলে সহজ clarification, আর uncertain inference ব্যবহারকারীকে জানাও।
- Durable preference কেবল verified user-এর স্পষ্ট সম্মতিতে এবং সীমিত key/value allowlist-এ: যেমন preferred language, বিস্তারিত/সংক্ষিপ্ত, timezone। UI-তে কী মনে আছে, কেন, কতদিন ও কীভাবে delete করা যায় দেখাতে হবে। Current conversation, profile এবং shared knowledge আলাদা boundary।
- Feedback voluntary ও purpose-specific: যেমন ভালো/খারাপ, reason category, নিজের সংশোধিত answer। Default-এ raw chat/attachment সংরক্ষণ বা training export নয়; telemetry ও personalised memory-এর consent আলাদা। No manipulation, sensitive inference, covert profiling বা vulnerability exploitation।
- Human review মানেই একজনের পছন্দকে universal truth নয়। Bengali, Banglish, English, dialect, accessibility, cultural neutrality এবং privacy-related slices-এ balanced opt-in data; ছোট sample-এ outcome অনিশ্চয়তা প্রকাশ। Under-18 বা sensitive domains-এর জন্য আগে অতিরিক্ত policy ও appropriate consent review।

## 5. উন্নয়নের ধাপ ও গ্রহণযোগ্যতার মানদণ্ড

### P0 — ব্যক্তিগত সীমানা ও সত্যতা (আগে)
- সব chat/legacy/compat/API routes-এ verified principal, per-session guest isolation, expired/forged cookie rejection, CSRF ও tenant boundaries পরীক্ষিত করতে হবে। Shared `usr-anonymous` / `usr-guest` থেকে পরিচয়-অপ্রমাণিত history নিজে থেকে migrate করা যাবে না; user-verified reclaim বা expiry পরিকল্পনা প্রয়োজন। Static service keys are not end-user identities; compatibility migration জরুরি। স্থানীয় নতুন patch-এ generic signed credential-ও প্রতি key-তে আলাদা; guest/token rotation হলে আগের data স্বয়ংক্রিয়ভাবে ফিরবে না। একটি key শেয়ার করলে সেটি এক principal-ই থাকবে, তাই end-user isolation-এর জন্য পৃথক registered user identity দরকার।
- Stateful write একক ownership transaction, request ID সহ idempotency, stream retry-তে duplicate/stale turn prevention; attachment arrival ও tool-call correlation-এর end-to-end test।
- User-derived summary/memory/preferences ও retrieved content-কে privileged system instruction বানানো বন্ধ; prompt injection tests, trusted anchor ও untrusted data পৃথক। Tool permission server-side enforce, model-এর কথায় অনুমতি নয়।
- Silent failures-এর প্রকৃত behavior ঠিক করা, constitution test দুর্বল/skip বা baseline update নয়। Security-sensitive পরিবর্তনে human review এবং local/authorized staging পরীক্ষা।

### P1 — local evaluation ও evidence
- Existing golden runner-এ versioned, reviewed holdout suites যোগ: ownership, prompt injection, tool use, retrieval truthfulness, citation/source integrity, Bangla/Banglish, explicit preference, uncertainty, correction, duplicate/stale reply, date/timezone, attachments এবং false claims of search। Fixture tests এবং বাস্তব model run আলাদা রিপোর্ট।
- Per-slice sample count, pass/fail, latency p50/p95, timeout, refusal and unsafe action rates, token/requests ও provider price evidence প্রকাশ। Empty suite বা insufficient sample হলে `not evaluated`, pass নয়। Minimum sample thresholds owner আগে নির্ধারণ করবেন; random train/test leakage ও repeated users প্রতিরোধ করতে held-out cases আলাদা।
- Consent-যুক্ত, ব্যক্তিগত তথ্য সরানো feedback candidate + reproducible expectation হিসেবে সংরক্ষণ; test-first triage; পক্ষপাত ও annotation disagreement পরিমাপ।

### P2 — নিরাপদ candidate ingestion ও review
- কম খরচে existing CI-তে deterministic JSON parser + schema, byte/count/depth সীমা, source binding from GitHub metadata, idempotent source/revision-derived ID, quarantine status, structured failures এবং retry। Missing credentials, partial writes, reviewer authority বা destination অজানা হলে success নয়। PR untrusted execution-এ production secrets দেবেন না।
- একটি আলাদা reviewer-controlled promotion mechanism ও audit trail, revocation, rollback; শুধু approved knowledge retrieve; retrieved record instruction নয়। Supabase schema, RLS/service-role ব্যবহারের পথ ও আপডেট atomicity আগে non-destructively যাচাই ও security review করতে হবে। কোনো table বা policy অনুমান করে production-এ পরিবর্তন নয়।
- Source spoof, prompt injection, secret/PII, duplicate, deleted/revoked ও conflicting facts regression tests; high-risk content human review ছাড়া publish নয়।

### P3 — সীমিত ও তুলনামূলক serving
- Task/locale ও user consent অনুযায়ী approved ছোট context retrieve; stable token/byte cap, relevance threshold এবং প্রয়োজনীয় কম তথ্য। Records না থাকলে সরাসরি উত্তর বা uncertainty; invented search/tool success নয়। একই প্রশ্নে baseline বনাম retrieval-on, matched traffic/held-out evaluation; slice-এ regression হলে rollout বন্ধ/rollback।
- Shared knowledge reads-এর cache কেবল non-critical; stale content হলে version/TTL/revocation check। Auth, quota, consent, writes ও approval-এর জন্য fail-closed; cached authorization fallback নয়।

### P4 — weight training কেবল আলাদা অনুমোদনে
- পরীক্ষায় নির্ভরযোগ্য gap থেকে গেলে, ব্যক্তিগত user data নয় এমন licensed বা explicit training-consent dataset, provenance ও deletion policy সহ local offline LoRA experiment বিবেচনা। Reproducible base/model licence/hardware, train/holdout separation এবং safety eval আগে। GPU/energy/engineering cost থাকলে তা $0 বলা যাবে না। উন্নতি না হলে model unchanged রেখে ফিরে যাও।

## 6. খরচের কার্যকর নিয়ন্ত্রণ

| Resource | পর্যবেক্ষণ | Limit ও failure behavior |
|---|---|---|
| Inference + relay | provider/model, approved free price evidence, request/token quota, usage ও latency | expired/unknown free approval বা paid fallback হলে reject; `unavailable` দেখাও; web-session policy/terms মেনে চলা আবশ্যক |
| Storage/Supabase | DB bytes, requests, egress, retention, free-plan limits; consent/delete success | hard usage cap/TTL; no silent overwrite or paid upgrade; privacy-critical writes fail closed |
| Redis | actual quota dashboard + monitor estimate, burn rate/window ও safety margin | যাচাই করে limit নির্ধারণ; কেবল non-critical read-এ bounded local fallback, auth/revocation/write-এ নয় |
| GitHub CI | runner minutes, artifact storage, concurrency | path-filtered focused tests, finite retention, self-hosted capacity থাকলে ব্যবহার; protected gates বাদ নয় |
| Logs/evals | aggregate counts, bounded sample, retention; opt-in real feedback | no secrets/PII; test budget capped; local fixtures নকল live quality নয় |

শুরুতে **কোনো provider-এর বাস্তব limit অনুমান নয়**। প্রথমে বর্তমান account-এর read-only billing ও usage মাপুন; projected usage-সহ operator-approved thresholds নির্ধারণ করুন; provider budget বা price অনিশ্চিত হলে paid route বন্ধ রাখুন। Alerts fail হলে unknown দেখাতে হবে।

## 7. Rollout ও governance

- Staging/local-এ cross-user, signed/expired/forged guest, CSRF, reset/renewal, concurrency, prompt injection, withdrawal এবং quota-exhaustion test; production-এ destructive/security/load পরীক্ষা নয়।
- Human approval for auth, user data, model-serving policy এবং spend-affecting changes; পূর্বের unified pipeline যথেষ্ট হলে দ্বিতীয় auto-merge path নয়। Feature flags + canary + metrics + instant disable/rollback।
- Success = নিরাপত্তা ও consent gate পাস, প্রয়োজনীয় slices-এ measurable improvement এবং budget evidence; শুধু CI green, JSON সংগ্রহ, inference বা একটি আত্মবিশ্বাসী rationale নয়। বন্ধ হলে পূর্বের approved system এবং পূর্বাবস্থায় ফিরে যাওয়ার প্রক্রিয়া যাচাই করতে হবে।

## 8. স্থানীয় personal-memory prototype: বাস্তব ঝুঁকি ও সীমা

এই অংশ **local, uncommitted prototype**, production deployment বা নিরাপত্তা-অনুমোদন নয়। এটি পুরোনো কথোপকথনের মালিকভিত্তিক সাম্প্রতিক history/summary ব্যবহার করতে পারে; সব পুরোনো conversation থেকে স্বয়ংক্রিয়ভাবে profile তৈরি বা legacy memory migrate করে না। নতুন personal memory কেবল সম্মতির পর নতুন chat-এর শেষ user turn থেকে নাম, ভাষা, পেশা, উত্তর-স্টাইল ও tech stack-এর নির্বাচিত regex match রাখে। একই user-এর নতুন explicit request-কে পুরোনো preference-এর উপরে রাখতে compiler-এ নির্দেশ আছে; ambiguous material requirement-এ ২–৪টি প্রাসঙ্গিক বিকল্প ও অন্য উত্তর দেওয়ার সুযোগ চাইতে নির্দেশ দেওয়া হয়েছে। এটি prompt-level আচরণ, model সবসময় মানবে বা ঠিকঠাক উত্তর দেবে তার প্রমাণ নয়।

### API ও সম্মতির অর্থ

- ব্যক্তিগত access-এর জন্য নিবন্ধিত পৃথক account-এর signed `Authorization: Bearer ...` প্রয়োজন; guest cookie, generic service key এবং shared `studio-admin` থেকে এই API ব্যবহার করা যায় না। বর্তমান identity resolver কেবল `usr-usr-<12 hex>` local account token সমর্থন করে; Supabase UUID-ভিত্তিক identity, shared admin, account linking ও token lifecycle আলাদাভাবে যাচাই/মেরামত ছাড়া এই সুবিধার আওতায় নয়। একটি bearer ভাগ করলে বহনকারীরা একই ব্যক্তি হিসেবে গণ্য হবে।
- `GET /api/v1/personal-memory`: policy version, উদ্দেশ্য, সীমা, consent state ও সংরক্ষিত entries দেখায়, consent বন্ধ থাকলেও deletion-এর সুবিধার্থে entries দেখায়; response `Cache-Control: no-store`। UI-তে আগে policy স্পষ্টভাবে দেখাতে হবে।
- `PUT /api/v1/personal-memory/consent`-এ `{"enabled": true, "policy_version": "personal-memory-v1"}` স্পষ্ট opt-in; version ছাড়া চালু হয় না। `{"enabled": false}` বন্ধ করে, তবে entries মুছে ফেলে না। সচেতন সম্মতি নিশ্চিত করতে UI, accessibility, বোধগম্য বাংলা অনুবাদ ও পৃথক user action দরকার; শুধু API acknowledgement সেগুলোর বিকল্প নয়।
- `DELETE /api/v1/personal-memory` সব local prototype entries এবং `?key=user_name`-এর মতো নির্বাচিত key মুছে দেয়; অন্য user-এর ID নেওয়া হয় না। এটি পুরোনো `user_memories`, Supabase/cloud, chat transcript, provider copy, backup বা SQLite/WAL-এর অবশিষ্ট data মোছে না। বিকল্পগুলোর জন্য আলাদা audited deletion প্রক্রিয়া দরকার; deletion-এর ফল বাড়িয়ে বলা যাবে না।
- Read/consent/write/delete SQLite ব্যর্থ হলে error ফেরে; chat route আর পূর্বের `ingest_turn_user_memories` legacy cloud auto-sync চালায় না। তবে codebase-এর পুরোনো memory/cloud helper অন্য caller-এ এখনও থাকতে পারে এবং অন্য subsystem-এর privacy audit করা হয়নি।

### সমস্যা → বর্তমান সীমিত সমাধান → অবশিষ্ট কাজ

1. **ভুল ব্যক্তি/CSRF:** অনুমানযোগ্য user ID বা cookie দিয়ে consent নয়; signed explicit bearer ও per-user SQL condition। Bearer চুরি, XSS, account recovery, key revocation, sign-out ও অন্য route-এর CSRF পূর্ণ সমাধান নয়। Shared admin ও non-local identity ইচ্ছাকৃতভাবে blocked। Security review এবং স্থানীয়/অনুমোদিত staging-এ পরীক্ষা আবশ্যক।
2. **অজান্তে সংগ্রহ/ভুল অনুমান:** default off; সীমিত key, শুধু নতুন শেষ user text; মডেলকে data হিসেবে উপস্থাপন। Regex মিথ্যা match করতে পারে, সংবেদনশীল তথ্য বা prompt injection সম্পূর্ণ শনাক্ত করতে পারে না, quoted text-ও ভুল বুঝতে পারে। UI-তে entries দেখানো, সম্পাদনা/নির্বাচিত deletion, স্পষ্ট উৎস ও confirmation; sensitive-category exclusion এবং expiry/retention control প্রয়োজন। আগে থেকে থাকা profile থেকে sensitive trait অনুমান নয়।
3. **Consent প্রত্যাহার/দৌড়:** SQLite transaction-এ consent দেখে লিখে; বন্ধ হলে পরবর্তী read-এ memory যায় না, আর disabled অবস্থাতেও delete সম্ভব। আগে compile হয়ে provider-এ পাঠানো request প্রত্যাহার করা যাবে না। Multiple replicas-এ আলাদা SQLite disk থাকলে consent/delete অসমন্বিত; shared consistent storage, transactional revocation, backfill/deletion ও rollout পরিকল্পনা ছাড়া multi-instance production নয়।
4. **সার্ভার restart ও $0:** SQLite স্থানীয় ও কম খরচের, কিন্তু ephemeral disk/redeploy-এ হারাতে পারে; persistent volume, concurrency/WAL, backups, encryption/access control, retention ও বাস্তব খরচ যাচাই হয়নি। Hard $0 বা সীমাহীন scale/availability দাবি করা যায় না। অপারেশনাল খরচ বা paid storage থাকলে আলাদা অনুমোদন প্রয়োজন।
5. **Provider ও injection:** memory প্রাসঙ্গিক হলে request-এর untrusted user-role context হিসেবে model provider-এ যেতে পারে; অন্যের সঙ্গে shared knowledge বা weight training-এ এই prototype পাঠায় না, কিন্তু provider retention/training policy ও downstream tool/model আচরণ এখানে প্রমাণিত নয়। Role separation একাই prompt-injection প্রতিরক্ষা নয়; tool authorization server-side থাকতে হবে।
6. **অন্য AI-এর memory:** এখন কোনো import/connector সক্রিয় নয়। ভবিষ্যতে per-user authenticated connection, উৎসের scope ও license, আলাদা explicit import consent, preview/select, provenance, validation, conflict resolution, revocation ও delete propagation ছাড়া sync নয়। Connected app চালু থাকাই user memory import-এর সম্মতি নয়।
7. **পুরোনো conversation ও consistency:** কেবল একই owned conversation-এর সীমিত history এই chat path-এ ব্যবহার হয়; account-এর সব পুরোনো conversation থেকে preference আহরণ বা cross-conversation semantic search নেই। কোনো unverified/shared-identity history নিজে থেকে migrate নয়। Fast-path response ও অন্যান্য chat routes এই নতুন ingestion path অতিক্রম নাও করতে পারে; end-to-end frontend coverage প্রয়োজন।
8. **অস্পষ্ট অনুরোধ:** model-কে বিকল্পসহ clarification চাইতে বলা হয়েছে; কোনো deterministic response gate বা live-model quality evaluation নয়। Action execution-এ confirmation/authorization আলাদা server-side পরীক্ষা আবশ্যক।

এই prototype-এ ব্যক্তিগত memory, reviewed shared decision-pattern এবং model training তিনটি পৃথক সীমানা। স্থানীয় fixture পরীক্ষা live provider quality, deployed SHA, privacy certification বা production cost যাচাই প্রমাণ করে না। Human review, feature flag ও অনুমোদিত staging পরীক্ষা ছাড়া rollout করা উচিত নয়।

পরীক্ষা-নোট: consent row-তে বর্তমানে শুধু সর্বশেষ enabled flag ও সময় থাকে; acknowledged policy version, consent event history এবং স্বাধীন audit log সংরক্ষিত নয়। এগুলো, UI সম্মতির যাচাই ও যুক্তিসঙ্গত retention policy production-পূর্ব শর্ত। Local focused suite-এ ব্যক্তিগত memory সহ 145টি test পাস হয়েছে; অতিরিক্ত `test_api_chat.py`, `test_auth_routes.py`, `test_stream_chat_contract.py` সংগ্রহে পরিবেশে `pydantic_settings`/`jwt` না থাকায় বাধা পেয়েছে। পৃথক upload-list suite-এ `client` fixture অনুপস্থিত: পাঁচটি setup error; অন্য 27টি test পাস। এগুলোকে pass বা live validation ধরা যাবে না।

## 9. Legacy shared-knowledge পথের স্থানীয় fail-closed পরিবর্তন

`ai_knowledge_exchange.py` ও `ingest_pr_knowledge.py`-এর এই branch-এর নতুন **local patch** অনিরীক্ষিত legacy packet/envelope থেকে Supabase `knowledge_base`, `learned_facts` বা Qdrant-এ কোনো write/embedding করে না। Live ingestion চাওয়া হলে non-zero error; explicit `--dry-run` কেবল সীমিত validation, raw packet/diff না দেখিয়ে জানায় যে কিছু সংরক্ষণ/অনুমোদন করা হয়নি। GitHub source read ব্যর্থ বা অসম্পূর্ণ হলে সফল দেখায় না। পুরোনো `active` rows-এর briefing export-ও বন্ধ: row-এর status বা agent-এর নিজের পরিচয় independent approval নয়। `decision_records.py` এখনও read-only, fixed-vocabulary candidate তৈরি করে; সেটি storage, approval বা runtime sharing নয়।

এটি deployment নয় এবং পুরোনো Supabase/Qdrant records বা backup মুছে দেয় না। বর্তমান workflow এখনও এই legacy command ডাকে; যাচাইযোগ্য evidence পেলে **ইচ্ছাকৃতভাবে job ব্যর্থ হবে**, নিঃশব্দে pass হবে না। স্বাধীন reviewer-controlled quarantine, immutable source ও revision, consent, approval/revocation audit, নিরাপদ পুনরুদ্ধার এবং frontend integration সম্পূর্ণ না হওয়া পর্যন্ত এটিকে পুনরায় চালু করা যাবে না। Existing production pipeline বদলানো হয়নি; UI, cross-conversation import, connected-AI import, live quality evaluation, সব auth path ও deletion propagation এখনও বাকি।

এই guard **সব learning path বন্ধ করে না**: `scripts/ci/kaggle_learning_bridge.py` এবং `core/api/routes/kaggle.py`-তে আলাদা active knowledge/fact ও vector write path রয়েছে; `core/memory/supabase_store.py`-তেও অন্য shared fact লেখার ও পড়ার পথ আছে। এগুলো এবং downstream consumers আলাদাভাবে audit ও নিয়ন্ত্রণ না করা পর্যন্ত সর্বব্যাপী quarantine বা isolation দাবি করা যাবে না। `ingest_pr_knowledge.py`-এর ingestion এখন diff আনে না, কিন্তু পৃথক `--query-pr` এখনও raw diff print এবং local archive তৈরি করতে পারে; `--query-file` পুরোনো Supabase metadata পড়তে পারে। এসব CLI-তে সংবেদনশীল repo/data ব্যবহার বন্ধ রেখে আলাদা privacy review প্রয়োজন; পুরোনো archive এ patch মোছে না।
