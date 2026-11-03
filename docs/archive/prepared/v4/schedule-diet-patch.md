# v4 Schedule-Diet Patch — হুবহু পরিবর্তন-স্পেসিফিকেশন

> বাংলা: cutover-সেশনের Phase E-ধাপ ২-এ এই দুই ফাইলের এই লাইনগুলোই বদলাতে হবে (fork main-এ commit)।
> যাচাই-উৎস: Task 38 workflow-স্ক্যান (৩৯ scheduled runs/day)। লক্ষ্য: ≈৭ run/day।

## ১) `.github/workflows/continuous-agent-loop.yml`

```yaml
# আগে (যাচাইকৃত, লাইন-স্তরে):
schedule:
- cron: "0 * * * *"   # COST OPTIMIZATION: hourly (was */30, originally */10)

# পরে:
schedule:
- cron: "0 2,8,14,20 * * *"   # v4-ডায়েট: ২৪→৪ run/day (ADR-007; কোটা ২,০০০-পুল রক্ষা)
```

- `workflow_dispatch` অক্ষত থাকবে — জরুরি মুহূর্তে হাতে চালানো যাবে।
- issue-opened real-time trigger-অংশ অক্ষত (সেটা schedule-নয়, কোটায় মাপা যায় না এভাবে)।

## ২) Nightly Ops workflow (`🔧 Nightly Ops & Maintenance` — সঠিক ফাইল-নাম cutover-সেশনে গাছ থেকে নিশ্চিত করে নেবে; বর্তমানে ৯টি cron-লাইন)

```yaml
# নিয়ম: ৯টি cron-এর মধ্যে মাত্র ১টি থাকবে — সম্ভব হলে সবচেয়ে হালকা একত্রিত-নাইটলি;
# বাকি ৮টি cron-লাইন মুছে/কমেন্ট করে একটি একক রাখা:
schedule:
- cron: "30 1 * * *"   # v4-ডায়েট: ৯→১ run/day (বাকি সব dispatch-only)
```

- ভেতরের job গুলো `workflow_dispatch`-inputs দিয়ে আলাদাভাবে চালানোর পথ খোলা রাখতে হবে (কিছু ফাইলে ইতিমধ্যে inputs-প্যাটার্ন আছে — Task 25-29-এ nightly-ops dispatch 26→25-ক্যাপ শিক্ষা)।

## ৩) স্পর্ষ-নিষিদ্ধ (অপরিবর্তিত)

| Workflow | cron/day | কারণ |
|---|---|---|
| Auto-Sync Fork with Upstream (375977882) | ৪ | Phase B-তে **disable**-ই হবে — ডায়েটের দরকার নেই |
| Issue Ops | ১ | হালকা, রাখা হলো |
| Code Quality Checks | ১ | হালকা, রাখা হলো |
| Smart Deploy Scheduler | ০ | অলরেডি retired→dispatch |

## প্রত্যাশিত ফল

- runs/day: ৩৯ → **≈৭** (৪ Agent Loop + ১ Nightly + ১ Issue Ops + ১ Code Quality)
- মাসিক-আনুমানিক: ২১০ run × ২–৩ মিনি ≈ **৪২০–৬৩০ মিনি** → ২,০০০-পুলে >১,৩০০ উদ্বৃত্ত (৭ private satellite-এর শেয়ার্ড-পুলসহ)
