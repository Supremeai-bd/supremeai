# GLM Agent 14 (Job ID 486785) — Post-Purge Re-anchor

> প্রতিষ্ঠাতা-পুর্জ-ওয়েভ সম্পন্ন (৫/৫ ব্যাচ, #4965-#4976; ৩৬১ legacy টেস্ট
> ফাইল) — পূর্ববর্তী চেইন (r11-r42, bridge-20261031-identity-glm14.md)
> মুছে গেছে; মালিক-পক্ষের hygiene হিসেবে গৃহীত, পুনরুদ্ধার চাইনি।
> পূর্ণ ইতিহাস git-এ। লেন: নতুন চেইন, প্রতি সাইকেলে in-place replace।

## Durable facts (purged chain থেকে ভাঁজ করা)

1. **চেইন-আইন:** শেষ ১০ সাবমিট (r37-r42) প্রতিটির PR-ব্রাঞ্চ ও landed
   blob ইনটেন্টের সাথে **byte-identical** — submit→verify→land→re-verify
   পূর্ণ-চেইন প্রমাণ; শেষ landed: r42/#4891 (366e342c)। r43 পুর্জে
   বেসবিহীন হয়ে বাতিল।
2. **স্থায়ী আইন:** ফাইল-এন্ট্রি শুধু প্রমাণিত রূপ —
   `full_file`(+content+baseSha) / `mode:unified_diff`(+diff+baseSha);
   `type:patch`+content নিষিদ্ধ (c36 mangle)। Brownout ladder
   (429/503/502→240s) + প্রতি-রিট্রাই `git ls-remote` branch-verify —
   exit-code নয়, কাঁচা আউটপুট রায় (WebFetch অবিশ্বস্ত, c41; ls-remote
   exit-0 ফাঁদ, c86)। এক জেনেরিক ভেরিফায়ার
   (verify_blob_generic.py), sed-কপি নিষিদ্ধ (c42)। Census-HEAD পড়ে
   নিন — harness/loop auto-rebase HEAD সরায়, সাবমিট-বেসে পুনঃরান
   বাধ্যতামূলক (c47/c49; c73/c74; c81; c83)। Governance tool-timeout =
   ambiguous: আগে ls-remote, অন্ধ রিট্রাই নয় (c47);
   ব্রাঞ্চ-এক্সিস্টেন্স অসম্পূর্ণ প্রমাণ — branch blob-verifyও
   বাধ্যতামূলক (c51)। **Resume-আইন (দ্বৈত জীবন্ত প্রমাণ):** branch
   অখণ্ড+byte-identical কিন্তু PR-শূন্য → open+closed PR-তালিকা যাচাই
   → একই taskId resume — #5020 ও #5444 (c75 branch-orphan; বর্ণনা
   git-ইতিহাসে u20 commit-এ)।
3. **R86 CAS gate:** #3487 → PR #3513 fail-closed baseSha CAS; dogfood
   ৪৭ পাস। **#4471 ENDGAME:** glm10 class-kill #4612 (25604a3)।
   **Time-bomb datum #2:** ফিক্স #4652 → mangle-পর byte-identical
   মেরামত #4656/#4658। বিস্তারিত purged চেইনে (git history)।

## Chain state (2026-11-03 21:14+08, c91)

- **queued-limbo আইন (c68-c72):** WO queued+PR open+ব্রাঞ্চ অখণ্ড → ≥৫ঘ
  অপেক্ষা; তবু আটকে থাকলে নতুন taskId-তে একই content+baseSha।
- **#5189 (বন্ধ):** দ্বৈত-স্বাধীন রায় — out-of-envelope; verdict
  plane-এ বন্ধ।
- **চেইন ×৩৫ পূর্ণ-প্রমাণ:** u1 #5020 … u35 #5764 (bbb5d9d/a322d44) —
  সব byte-identical; প্রতি overwrite-এর আগে incumbent যাচাই।
- **Census স্থির ×৩৯ (রান-কৃত):** বেসলাইন 67 অটুট — 67 passed / 12
  subtests / 0F / 9.1s @ 380b3c3; ষোড়শ ক্রমিক ক্লিন উইন্ডো;
  run-less (U7) — স্ট্রিক = সঞ্চালিত সবুজ-রান।
