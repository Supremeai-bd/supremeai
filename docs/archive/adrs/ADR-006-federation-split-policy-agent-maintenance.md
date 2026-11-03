# ADR-006: ফেডারেশন-বিভাজন নীতি ও মাল্টি-রিপো এজেন্ট-রক্ষণা পরিকল্পনা

- তারিখ: 2026-10-08 (Asia/Dhaka)
- স্ট্যাটাস: **Proposed** (ব্যবহারকারীর সিদ্ধান্ত বাকি)
- প্রসঙ্গ: ব্যবহারকারীর দুটি প্রশ্ন — ① "agents work only on one repo... in future how will agents do that?" ② "browser, mcp tower similarly many feature can be individual repo... what do you think"

## Context

- বর্তমান federation (টপোলজি v3, ADR-005): fork supremeai (লাইভ মনোলিথ+CI) + api, core, infrastructure, mcp-control-plane, sdk, studio, open + supremeai-archive (খাতা)
- বাস্তব-শিক্ষা (প্রমাণসহ): studio extraction (৭২৪ path/৫৬৫ code) প্রমাণিত প্যাটার্ন; **Duplicate Logic Detector CI-ই** scout/dedup.py ≡ ecosystem_scout/dedup.py ধরেছে (Deep-Audit #17) — অর্থাৎ duplicate-শনাক্তকরণের সঠিক যন্ত্র **CI, repo-সীমা নয়**
- User-অ্যাকাউন্ট (org নয়) → org-secrets নেই → প্রতিটি নতুন রিপো = secret-প্রতিলিপি + নতুন CI-সেট বাড়ে (এই সেশনেই ২৪ secret ভরাটের খাটুনি দেখা গেছে)

## Decision (প্রস্তাব)

### ১. বিভাজন-নীতি — নিম্নোক্তের **≥২** পূরণ হলে তবেই split
- স্বতন্ত্র deploy/release চক্র (যেমন store-release)
- স্বতন্ত্র versioning/semver-দরকার
- পৃথক রানটাইম-প্ল্যাটফর্ম (extension vs server vs worker)
- monolith CI-বোঝা প্রমাণিত বাধা

**শুধু duplicate-ভয়ে split নয়** — duplicate খোঁজার দায়িত্ব federation-contracts CI + Duplicate Logic Detector-এর; রিপো-সীমা নয়।

### ২. প্রার্থী-মূল্যায়ন (ব্যবহারকারীর নাম-উল্লিখিত)
| প্রার্থী | রায় | কারণ |
|---|---|---|
| **browser** | ✓ ভালো প্রার্থী | স্বতন্ত্র store-release + পৃথক প্ল্যাটফর্ম — নীতির ৩/৪ শর্ত পূরণ |
| **mcp tower** | নতুন রিপো **দরকার নেই** | supremeai-mcp-control-plane (১৭৬ path/১৩৩ code) ইতিমধ্যেই তার বাসা; দরকার = সেখানেই বিস্তার + contracts-check জোরদার |
| studio/sdk/api | ইতিমধ্যে extracted ✓ | প্রমাণিত প্যাটার্ন |
| বাকি সব | monolith-spine-এ | integration-সত্যের একমাত্র জায়গা |

### ৩. মাল্টি-রিপো এজেন্ট-রক্ষণা — ৫-স্তম্ভ
1. **প্রতি রিপোতে `AGENTS.md`** — ভূমিকা, CI-গেট, secret-নাম, deploy-লক্ষ্য; এজেন্ট শুধু যে রিপো স্পর্ষ করবে তার bootstrap পড়বে (কনটেক্সট-খরচ নিয়ন্ত্রণে)
2. **repo-registry** — infrastructure-এর MANDATORY_REPOS বর্ধিত করে এক-ফাইল federation-ম্যাপ (রিপো × ভূমিকা × visibility × owner-workflow)
3. **contracts-CI-ই integration-সত্য** — এজেন্ট সব কোড মনে রাখে না; parity-check ব্যর্থ হলেই ভাঙা-সেলাই ধরা পড়বে (federation_contracts_check.py প্রমাণিত মডেল)
4. **archive-ledger একমাত্র সিদ্ধান্ত-উৎস** — প্রতিটি এজেন্ট-সেশন worklog-tail + ADR + lessons থেকে bootstrap (এই সেশনে বারবার প্রমাণিত: L-003 playbook দিয়ে মিনিটে পুনরুদ্ধার)
5. **একক identity-plane** — App-token (স্বল্পায়ু, runtime-মিন্ট) + Infisical vault; দীর্ঘ-lived key এজেন্টের হাতে থাকবে না (মিরর-ক্রেডেনশিয়াল প্রমাণ: ADR-005 execution log)

## Consequences

- ধনাত্মক: বিভাজন-সিদ্ধান্ত আর মতভেদ-নির্ভর নয়, নীতি-নির্ভর; নতুন এজেন্ট-সেশন মিনিটে bootstrap; secret-বিস্তার নিয়ন্ত্রিত; duplicate-প্রশ্নের একটাই উত্তর-যন্ত্র
- ঝুঁকি: অতি-বিভাজন = cross-repo PR-জটিলতা + প্রতি-রিপো secret-খাটুনি; তাই প্রতিটি split-এর **আগে** contracts-check ও AGENTS.md রেডি থাকবে — "split, then wire" নয় — "wire, then split"
- পর্যালোচনা: প্রতি নতুন split-প্রস্তাবে এই ADR-এর নীতিতে মাপা হবে; নীতি-ব্যতিক্রমে নতুন ADR
