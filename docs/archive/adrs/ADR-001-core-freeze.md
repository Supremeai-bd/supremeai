# ADR-001: `core` রিপো (Phase 5) হিমশীতল রাখা

- **তারিখ:** ২০২৬-১০ (মূল রায় Task 24 audit-এ; এখানে স্থায়ী করা হলো)
- **Status:** Accepted

## Context
Roadmap-এ Phase 5 Core extraction আছে; কিন্তু federation-এর বাকি অংশ (Gateway P0–P4, CI স্বাস্থ্য) তখনো পরিপক্ব হয়নি। ৩৬টি core import-এর মধ্যে ২৩টি logging_config — তখনই বিচ্ছিন্ন করলে অর্থহীন শাফলিং।

## Decision
`core` রিপো ইচ্ছাকৃতভাবে খালি ও হিমশীতল (0 code = deliberate); কোনো extraction কাজ এখনে হবে না।

## Consequences
- ✅ জটিলতা কম; খালি রিপোর শৃঙ্খলা স্পষ্ট।
- ⏳ ভবিষ্যৎ extraction-এ আগে logging-decoupling লাগবে (ADR-002)।
