# API-key revocation: স্থানীয় নিরাপত্তা সংশোধন ও rollout সীমা

## সমস্যা ও প্রতিকার

Core API-key middleware আগে Redis-এ পাওয়া সক্রিয় key row-কে সর্বোচ্চ পাঁচ মিনিট authentication-এর ভিত্তি হিসেবে ব্যবহার করত। Revoke/delete/rotate-এর পরে cache invalidation ব্যর্থ হলে, বা পুরোনো read আবার cache লিখলে, stale active row দিয়ে পূর্বের key গ্রহণ হতে পারত। Invalid key এবং database outage—দুটিকেই একই 401 হিসাবে দেখানো হতো।

স্থানীয় patch-এ প্রতিটি API-key authentication authoritative database থেকে যাচাই হয়; Redis-এর cached authorization verdict পড়া বা লেখা হয় না। DB-তে অনুপস্থিত key → 401; revoked key → 403; DB বা circuit breaker unavailable → 503, cached allow-তে fallback নয়। বিদ্যমান `_get_cached_api_key` নামটি call-site/test compatibility-র জন্য রাখা হয়েছে; বাস্তবে এটি আর cache পড়ে না।

## সীমাবদ্ধতা ও rollout-এর আগে

- এটি **local, uncommitted patch**; production deployment বা সব authentication path সুরক্ষিত হওয়ার প্রমাণ নয়। Signed gateway/session token এবং অন্য সার্ভিসের authentication আলাদাভাবে audit করতে হবে।
- সব serving replica-তে সংশোধন না পৌঁছানো পর্যন্ত পুরোনো replica এখনও stale Redis row গ্রহণ করতে পারে। Rolling deployment ও rollback-এ পুরোনো cache ব্যবহার পুনরায় সক্রিয় হওয়ার ঝুঁকি আছে; নিরাপদ rollout, পুরোনো replica drain, cache expiry/invalidation ও human security review প্রয়োজন।
- সফল DB lookup-এর পর concurrent revoke হলে ইতিমধ্যে অনুমোদিত in-flight request চলতে পারে; দীর্ঘমেয়াদি stream/action-এর পুনঃযাচাই এই patch-এ নেই। Primary/authoritative database-এর consistency দরকার; stale read replica revocation নিশ্চয়তা দিতে পারে না।
- প্রতি key request-এ DB read বাড়বে: latency, connection pool, DB quota ও billed usage **মাপা হয়নি**। Strict $0, সর্বোচ্চ throughput বা availability দাবি নয়। Security-sensitive authentication-এ Redis বা process-local cached allow fallback চালু করা যাবে না।
- SQLite personal-memory consent, external AI import, cross-conversation backfill, UI, deletion propagation এবং live-model clarification quality এর দ্বারা সমাধান হয়নি।
- স্থানীয় fake DB/Redis পরীক্ষায় revoke/delete/rotate-পরবর্তী stale cache, DB outage, open circuit ও scope update পরীক্ষা করা হয়েছে। Focused gateway/auth/memory suite: ১৯২ passed, ২ warnings। এগুলো production deploy, load test বা real database concurrency-এর বিকল্প নয়; কেবল local/অনুমোদিত staging-এ security ও load test করুন।
- বর্তমান `main`-এর আলাদা clean checkout-এ constitution suite: ২২৯ passed, ১১ failed, ১ skipped; silent-error scanner: ১৩২টি নতুন high finding, exit 1। `gateway/tests/test_api_keys.py`-এ ৮টি failure একই clean `main`-এও দেখা গেছে; এগুলোর কয়েকটি credential ছাড়া ২০০ প্রত্যাশা করে। Security bypass বা test দুর্বল করে pass দেখানো হয়নি।
