# ADR-003: Main repo সম্পূর্ণ হিমশীতল + best-of consolidation কৌশল

- **তারিখ:** ২০২৬-১০-০৭ (ব্যবহারকারীর সিদ্ধান্ত)
- **Status:** Accepted — Task 24-এর "Tier 1 first" পরবর্তী-পদক্ষেপ সুপারিশকে supersede করে

## Context
Federation-এর main repo (`paykaribazaronline/supremeai` fork) এখন তার "সেরা অবস্থায়" — Roadmap §41-annotation (PR#31) পর্যন্ত সব কাজ সম্পন্ন (Task 25–29); বাকি ফাইন্ডিংগুলো production-স্বাস্থ্য-নির্ভর register (#23–26)। অন্যদিকে অন্য রিপোগুলোতে (sdk / studio / mcp-control-plane / infrastructure / supremeai-api / supremeai-open) কাজ চলমান।

## Decision (ব্যবহারকারীর নির্দেশ, হুবহু-অর্থে)
1. **এখন main repo-তে কোনো কাজ হবে না** — কোনো PR, commit, workflow-dispatch, issue-mutation নয়। লাল/সবুজ যা আছে তেমনই থাকবে।
2. **অন্য রিপোর চলমান কাজগুলো আগে শেষ হবে।**
3. **তারপর consolidation:** main repo-র সেরা অংশ + second repo-র সেরা অংশ একসাথে নেওয়া হবে।
4. **কিছুই বাদ যাবে না** — শুধু প্রতিটি জিনিসের ভালোটা যে-রিপোতে আছে সেখানেই adopt করা হবে।

## Consequences
- ✅ ঝুঁকি-হ্রাস: main repo-র স্থিতিশীল অবস্থা সংরক্ষিত; দুর্ঘটনাজনিত mutation-সম্ভাবনা শূন্য।
- ✅ এই archive-ই "কিছুই হারাবে না"-র গ্যারান্টি — `roadmap-snapshots/2026-10-07-supremeai-roadmap-FROZEN.md`-এ main repo-র হিমশীতল-মুহূর্তের প্রতিলিপি আছে (fork origin/main @ 37d0596c)।
- ⏸️ মুলতবি: fork housekeeping, উৎপাদন-ফাইন্ডিং #23–26-এর fork-সংশ্লিষ্ট কাজ, upstream #4160 (sharp-fix)-এর fleet-পথ।
- ▶️ চলমান (অনুমোদিত): শুধু অ-মেইন-রিপো কাজ — infrastructure / sdk / studio / mcp-control-plane / supremeai-api / supremeai-open।
- 📌 consolidation-এর সময় "second repo" কোনটি হবে তা স্পষ্ট করা হবে (বর্তমান অনুমান: supremeai-api Gateway — সবচেয়ে সক্রিয়)। অনুমান চূড়ান্ত নয়; সিদ্ধান্তের সময় এখানেই নথিভুক্ত হবে।
