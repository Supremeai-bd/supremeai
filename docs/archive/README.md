# supremeai-archive — ঐতিহাসিক সংগ্রহস্থল (Historical Archive)

> **একমাত্র উদ্দেশ্য:** গুরুত্বপূর্ণ পরিকল্পনা, সিদ্ধান্ত ও কাজের ইতিহাস কখনো হারাবে না।
> Purpose: append-only ledger of worklogs, decisions (ADR), roadmap snapshots and lessons for the SupremeAI federation.

## বর্তমান অবস্থা (Status banner — v4-decided, ADR-005+ADR-007)

- **লাইভ main = fork `paykaribazaronline/supremeai`** — cutover-পরে **PRIVATE** হবে (v4: Open-Core, ব্যবহারকারীর চূড়ান্ত সিদ্ধান্ত 2026-10-09)।
- **`SaifulHaqueNiloy/supremeai` = প্রাইভেট আর্কাইভ-মিরর** (ADR-005; flip = একমাত্র মানব-ক্লিক) — receive-only, `[skip ci]` mirror।
- **Public-ফেস = `supremeai-open`** — উৎস-রিপো থেকে projection-sync (gitleaks fail-closed গেট; generated-repo নীতি — সরাসরি মানব-push নয়)।
- **মিনিট-বাজেট (v4):** schedule-diet → ৩৯→≈৭ run/day ≈ ৪২০–৬৩০ মিনি/মাস (২,০০০-পুলে >১,৩০০ উদ্বৃত্ত)।
- **প্রস্তুতি-আর্টিফ্যাক্ট:** `prepared/v4/` (schedule-diet-patch + open-projection.yml) — cutover-সেশনে সরাসরি প্রয়োগ।
- cutover অবরুদ্ধ ৪ মানব-ক্লিকে: ①parent-flip ②GitHub App দ্বিতীয় অ্যাকাউন্টে ③Render re-point ④key-rotation (vault-এ নতুন মান)।

## কেন এই রিপো (Why)

1. **Sandbox reset ঝুঁকি (বাস্তবে ঘটেছে)** — এজেন্ট-স্যান্ডবক্স রিসেট হলে `/home/z/my-project/worklog.md` সহ সব লোকাল ফাইল মুছে যায়। কাজের ইতিহাস শুধু লোকালে থাকা = একটাই বিপর্যয় দূরে।
2. **Fork-নির্ভরতা** — roadmap-এর বাসা fork-এর `docs/plans/`-এ; fork upstream-এর সাথে বাঁধা, detach/delete হলে পরিকল্পনা ঝুঁকিতে।
3. **সিদ্ধান্ত ছড়িয়ে-ছিটিয়ে** — issues বন্ধ হয়, PR-branch merge-এর পরে মোছা যায়, চ্যাট ক্ষণস্থায়ী; স্থায়ী append-only খাতার অভাব ছিল।

## কাঠামো (Structure)

```
worklogs/           # কাজের খাতা — sandbox worklog.md-এর rolling mirror (Task 1 থেকে)
adrs/               # Architecture Decision Records — এক সিদ্ধান্ত = এক ফাইল
roadmap-snapshots/  # নির্দিষ্ট সময়ের roadmap প্রতিলিপি (fork commit-sha সহ)
lessons/            # distilled lessons — কী ভুল, কী শিখলাম, কীভাবে বাঁচব
legacy-specs/       # মূল রিপো থেকে স্থানান্তরিত ঐতিহাসিক মাস্টার স্পেক্স ও প্ল্যান
tarballs/           # ঐতিহাসিক ডকুমেন্টের সংকুচিত ব্যাকআপ (.tar.gz)
```

## নিয়ম (Conventions)

1. **Append-only** — পুরনো লেখা কখনো সম্পাদনা/মোছা নয়; শুধু নতুন এন্ট্রি যোগ হয়।
2. **শূন্য secret** — কোনো token/কী/credential এখানে কখনো আসবে না (শূন্য-প্রিন্ট, শূন্য-কমিট শৃঙ্খলা)।
3. **বাংলা মন্তব্য** — সব এন্ট্রিতে বাংলা ব্যাখ্যা + ইংরেজি টেকনিক্যাল টার্ম।
4. **প্রতি সেশনের শেষ ধাপ** — `/home/z/my-project/sync_archive.sh` চালিয়ে worklog মিরর + push।
5. **সরাসরি main push-এর ছাড় (নথিভুক্ত)** — এই রিপোতে code/CI নেই, শুধু ডকুমেন্ট; তাই 1 Issue=1 Branch=1 PR নীতি এখানে প্রযোজ্য নয় — সচেতন সিদ্ধান্ত।
6. **ADR ফরম্যাট** — Context → Decision → Consequences; এক পাতার মধ্যে; Status সহ।
7. **Snapshot ফরম্যাট** — প্রথমে মেটাডেটা ব্লক (তারিখ, উৎস-sha, কারণ), তারপর হুবহু ফাইল-বিষয়বস্তু।

## সিঙ্ক কীভাবে হয় (Sync)

স্যান্ডবক্সে `/home/z/my-project/sync_archive.sh` — worklog কপি করে, কমিট করে, push করে।
Sandbox reset হলে স্ক্রিপ্ট নিজেই রিপো আবার clone করে নেয় — তাই ইতিহাস কখনো হারায় না।
