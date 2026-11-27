# Nightly Actions ও HITL fail-closed পর্যালোচনা

## Actions evidence

- #919 merge-এর [main run 46041506046](https://github.com/Supremeai-bd/supremeai/actions/runs/46041506046) শেষ হয়েছে `success`। GitHub metadata অনুযায়ী Render-এর api/core/brain/worker/scraper deploy-and-verify jobs সফল, Cloudflare deploy path-filter-এর কারণে skipped। Job log সংগ্রহ EOF হওয়ায় বাস্তব provider behavior বা live chat প্রমাণিত নয়।
- পরবর্তী [nightly run 46042507262](https://github.com/Supremeai-bd/supremeai/actions/runs/46042507262) ব্যর্থ। Job metadata অনুযায়ী Redis quota monitor, full guard roster, silent-error scan, Windows self-hosted verification, local deep audit, platform deep audit, ZAP, constitution এবং chaos suite ব্যর্থ। GitHub log endpoints EOF দিয়েছে; metadata/annotations সম্পূর্ণ log-এর বিকল্প নয়।
- ZAP annotation অনুযায়ী explicit environment এবং `STAGING_BASE_URL` অনুপস্থিত। Production URL দিয়ে এটি পূরণ বা production-এ scan চালানো যাবে না। Redis monitor exit 3: quota check অসম্পূর্ণ; annotation থেকে মূল কারণ নিশ্চিত নয়। কাউকে secrets এখানে লিখতে বলা হচ্ছে না। Runner/deep-audit/chaos এবং guard roster-এর নির্দিষ্ট কারণ সম্পূর্ণ log ছাড়া নিশ্চিত নয়।
- Local constitution: 11 failed, 229 passed, 1 skipped (missing slot registry, bridge workflow/watchdog coupling, root package)। Silent scanner: baseline-এর বাইরে 130 high blocker; gate বা baseline পরিবর্তন করা হয়নি। সামগ্রিক সমাধান অসম্পূর্ণ।

## এই পরিবর্তনের পরিধি

Gateway `frontend_compat`-এর `/api/admin/control-plane/hitl/{hid}/resolve` এখন JSON object-এ explicit `approved`/`rejected` ছাড়া কিছু গ্রহণ করে না। অজানা, পুনরাবৃত্ত বা আর pending নয় এমন record resolve হয় না; duplicate registration-ও প্রত্যাখ্যাত। GitHub target validation, pending deployment preflight এবং upstream status যাচাই করা হয়; অনিশ্চিত mutation-কে success বলা বা একই process-এ আবার চালানো হয় না। একই record-এ deployment ও PR দুটিকে একসঙ্গে গ্রহণ করা হয় না, কারণ atomicity নিশ্চিত নয়। কোনো GitHub target না থাকলে local status change-ই ঘটে, response-এ external action করা হয়নি লেখা থাকে।

এটি canonical Core HITL routes বা অন্য অনুমোদন ব্যবস্থা বদলায় না। এই compatibility store in-memory ও process-local: restart, একাধিক replica, concurrency জুড়ে durable state, centralized idempotency ও reconciliation নেই। `indeterminate` অবস্থায় operator-কে GitHub-এর আসল অবস্থা যাচাই করতে হবে; এটি durable queue বা production-grade authorization/approval guarantee নয়। Admin authentication এই পরিবর্তনে শিথিল হয়নি। Tests-এ GitHub mocked; বাস্তব mutation চালানো হয়নি।
