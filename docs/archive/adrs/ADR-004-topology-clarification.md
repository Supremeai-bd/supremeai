# ADR-004: Federation topology-র চূড়ান্ত স্পষ্টীকরণ — প্রকৃত main বনাম test federation

- **তারিখ:** ২০২৬-১০-০৭ (ব্যবহারকারীর ব্যাখ্যা)
- **Status:** Accepted — ADR-003-এর খোলা প্রশ্নের ("second repo কোনটি") চূড়ান্ত উত্তর

## Context
ADR-003-এ "second repo" হিসেবে অনুমান ছিল supremeai-api। ব্যবহারকারী প্রকৃত টপোলজি ব্যাখ্যা করলেন: প্রকৃত উন্নয়ন চলে ভিন্ন অ্যাকাউন্টে, `paykaribazaronline` শুধু যাচাই-মাঠ।

## Decision (ব্যবহারকারীর ব্যাখ্যা, হুবহু-অর্থে)
1. **প্রকৃত main repo = `SaifulHaqueNiloy/supremeai`** — "আমাদের বাকি সব এই রিপোতে; আমি এখন main হিসেবে এখানেই কাজ করছি।"
2. **`paykaribazaronline`-এর একাধিক রিপো (fork supremeai + sdk / core / studio / mcp-control-plane / infrastructure / supremeai-api / supremeai-open / supremeai-archive) = পরীক্ষার মাঠ** — "সব ঠিকঠাক আছে কি না যাচাইয়ের জন্য।"
3. **Best-of consolidation-দিক:** test-federation-এর সেরা অংশ → প্রকৃত main-এ adopt; কিছুই বাদ নয়, শুধু প্রতিটি জিনিসের ভালোটা।

## প্রমাণ (API-probe, ২০২৬-১০-০৭)
- **Fork-parent CONFIRMED:** `paykaribazaronline/supremeai`.parent = `SaifulHaqueNiloy/supremeai` (source-ও একই)।
- প্রকৃত main: **public**, non-fork, branch=main, pushed=2026-10-07T19:11Z, ~40MB, 12 open issues; সর্বশেষ কমিট `d4c1cea3` (#4176 docs_garbage TREE sweep) — সক্রিয় উন্নয়ন চলছে।
- App-installation (`supremeai-3rd-party-platform`) **`SaifulHaqueNiloy` অ্যাকাউন্টে ইনস্টলড** → প্রকৃত main-এ এজেন্ট-অ্যাক্সেস বিদ্যমান।
- প্রকৃত main-এর লোকাল ক্লোন রক্ষা পেয়েছে: `/home/z/my-project/supremeai` (origin যাচাইকৃত) — কিন্তু **4156 dirty ফাইলযুক্ত সক্রিয় কার্যক্ষেত্র; এজেন্ট স্পর্ষ করবে না**।
- প্রকৃত main-এর নিজস্ব roadmap/docs আছে (`docs/ROADMAP.md` ইত্যাদি, issue-সিরিজ #41xx) — consolidation-এর সময় সেটিই সত্য-উৎস।

## Consequences
- ADR-003-এর "second repo = supremeai-api (অনুমান)" **সংশোধিত** → consolidation-গন্তব্য = `SaifulHaqueNiloy/supremeai`।
- পরিভাষা-চুক্তি (এই archive-এর সব ডকে): **"test-federation main"** = fork `paykaribazaronline/supremeai` (হিমশীতল); **"প্রকৃত main"** = `SaifulHaqueNiloy/supremeai`।
- ADR-003 freeze অটুট — শুধু fork-এ প্রযোজ্য; test federation যাচাই-মিশনে চলবে; প্রকৃত main ব্যবহারকারীর সক্রিয় এলাকা (নির্দেশ ছাড়া এজেন্ট স্পর্ষ করবে না)।
