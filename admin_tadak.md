# SupremeAI Manual Administration Tasks

এই তালিকাটি Phase 0–2-এর যেসব কাজ repository automation একা নিরাপদে সম্পন্ন করতে পারে না, সেগুলোর জন্য। প্রতিটি কাজ সম্পন্ন হলে owner, date, evidence link এবং decision log entry যোগ করতে হবে।

## Required manual approvals

- [ ] `baseline_commands.json`-এর deployment commands production-এ চালানোর আগে একজন owner অনুমোদন করবেন।
- [ ] CI advisory ফলাফল পর্যবেক্ষণ করে deterministic failure-কে blocking mode-এ উন্নীত করার সিদ্ধান্ত নিন।
- [ ] Protected path registry-এর business owner review সম্পন্ন করুন—বিশেষত auth, tenant isolation, billing, migration ও production configuration।
- [ ] Required environment variables-এর নাম ও build/runtime classification deployment owners যাচাই করুন; values কখনো commit করবেন না।
- [ ] Docker, Firebase, Render/GCP deployment credentials, health checks এবং rollback procedure বাস্তব পরিবেশে পরীক্ষা করুন।
- [ ] Database migration-এর rollback/restore drill manually চালান।
- [ ] CI artifact retention, evidence deletion এবং privacy policy-এর retention period অনুমোদন করুন।
- [ ] False-positive/false-negative baseline dataset review করে detector gate promotion অনুমোদন করুন।
- [ ] Autonomy level promotion কেবল engineering owner-এর লিখিত approval-এর পরে করুন।

## Not automated by design

- Production deploy, database migration, deletion, billing, auth বা tenant-isolation পরিবর্তন।
- Protected branch-এ সরাসরি push বা branch protection bypass।
- Secret values পড়া, model-এ পাঠানো, log/artifact-এ সংরক্ষণ।
- Flaky CI check quarantine করা—প্রতিটি owner ও expiry নির্ধারণ প্রয়োজন।
- AI-generated plan/evidence-কে independently verified হিসেবে চিহ্নিত করা।
- Ambiguous security finding বা unrestricted self-rewrite।

## Evidence to attach

- Repository/commit SHA
- Approval identity and timestamp
- Relevant CI run and artifact URL
- Deployment or rollback result
- Unresolved limitations and follow-up issue
