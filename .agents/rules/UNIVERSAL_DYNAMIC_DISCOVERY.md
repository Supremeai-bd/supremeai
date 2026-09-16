# 🌐 Rule: Universal Dynamic Discovery & Zero-Hardcoded Entities

> **Scope:** Repository-wide. Applies to all modules, circles, engines, agents, tools, and integrations within SupremeAI.  
> **Directives:** No unnecessary hardcoding of entities, brands, models, providers, quotas, or workflows where dynamic registration or discovery is possible.  
> **Source:** SupremeAI Global Architectural Principle (Roadmap §12–§16, §35–§38; AGENTS.md Mandatory Second Rule).

---

## ১. The Core Architectural Law (সর্বজনীন স্থাপত্য নীতি)

> **"If a value, entity, provider, model, integration, capability, resource, workflow, policy, or behavior can be discovered, registered, configured, or selected dynamically, it MUST NOT be unnecessarily hardcoded into application logic."**

SupremeAI-তে কোনো থার্ড-পার্টি সার্ভিস, ব্রাউজার প্ল্যাটফর্ম বা এআই প্রোভাইডারের নাম (যেমন: Bolt, Lovable, v0, OpenHands, কিংবা OpenAI, Anthropic, Gemini) সিস্টেমের কোর আর্কিটেকচারাল ডিসিশন বা কোড-লেভেল কনস্ট্রাক্ট হিসেবে স্থান পাবে না।

### Dynamic Pools ($1 \dots N$ Resources):
- আজ সিস্টেমে ৪টি প্রোভাইডার থাকতে পারে, ভবিষ্যতে ৪১তম প্রোভাইডার যোগ হলেও **কোর অর্কেস্ট্রেশন, স্টেট মেশিন বা রাউটিং লজিকের এক লাইন কোডও পরিবর্তন করা যাবে না**।
- সমস্ত সত্ত্বা (Entities) কনফিগারেশন, ডেটাবেস, এনভায়রনমেন্ট বা রেজিস্ট্রির মাধ্যমে ডায়নামিকালি লোড/ডিসকভার হবে।

---

## ২. Four Pillars of Dynamic Discovery

### ২.১ Pillar ১: Core Orchestration Knows Zero Brand Names
- কোর ইঞ্জিন ও কন্ট্রোল টাওয়ার কেবল **Capability Signatures** (`coding.plan.v1`, `coding.execute.v1`, `code.review.v1`, `reasoning.v1`) এবং **Runtime Attributes** (Health, Quota, Latency, Policy/ToS, Cost Tier) চিনবে।
- কোর কোডে কখনো এমন ব্রাঞ্চিং লেখা সম্পূর্ণ নিষিদ্ধ:
  ```python
  # ❌ সম্পূর্ণ নিষিদ্ধ (Hardcoded Provider Branching)
  if provider == "bolt":
      run_bolt_flow()
  elif provider == "lovable":
      run_lovable_flow()

  # ✅ বাধ্যতামূলক নিয়ম (Capability & Registry-Driven Placement)
  placement = runtime_selector.select_placement(
      capability_signature="coding.execute.v1",
      constraints=PlacementConstraints(quota_required=1, min_health="HEALTHY")
  )
  adapter = resource_registry.resolve_adapter(placement.resource)
  result = await adapter.execute(task_payload)
  ```

### ২.২ Pillar ২: Unified Provider Registry Contract
প্রতিটি প্রোভাইডার ও এক্সটার্নাল এজেন্ট একটি প্রমিত ডেটা স্ট্রাকচার হিসেবে রেজিস্ট্রি বা ডেটাবেসে সংরক্ষিত থাকবে:
```text
Provider Registry Record
 ├─ provider_id: str (UUID বা dynamic slug)
 ├─ display_name: str
 ├─ provider_kind: str (জেনেরিক ক্যাটাগরি, e.g., "external_agent_worker")
 ├─ capabilities: list[str] (e.g., ["coding.plan.v1", "coding.execute.v1"])
 ├─ integration_types: list[str] (["native_api", "mcp_tool", "browser_automation"])
 ├─ adapter_reference: str (dynamic dotted import path, e.g., "adapters.custom.CustomAdapter")
 ├─ health_status: ResourceState (HEALTHY | DEGRADED | OFFLINE)
 ├─ quota: QuotaProfile (free_tier_remaining, resets_at, rpm_limit)
 ├─ cost_tier: str (FREE | LOW_COST | PAID)
 ├─ latency_profile: str (FAST | MEDIUM | BATCH)
 ├─ policy_status: PolicyProfile (tos_risk_tier, hitl_required, allowed_tenants)
 └─ enabled: bool
```

### ২.৩ Pillar ৩: Sandboxed Adapters via Dynamic Import
- প্রোভাইডার-নির্দিষ্ট সমস্ত API কল, payload ফরম্যাটিং বা ব্রাউজার ইন্টারঅ্যাকশন কঠোরভাবে এর নিজস্ব **Adapter** ক্লাসের ভেতর সীমাবদ্ধ থাকবে।
- অ্যাডাপ্টার লোড হবে ডায়নামিকালি `importlib.import_module(module_path)` ব্যবহার করে।
- কোনো অ্যাডাপ্টার মিসিং থাকলে সিস্টেম ক্র্যাশ না করে গ্রেসফুল ফলব্যাক (Graceful Degradation / Alternative Placement) গ্রহণ করবে।

### ২.৪ Pillar ৪: Dynamic Quota & Health as First-Class Placement Criteria
- কোটা (Quota) এবং হেলথ (Health) কোনো স্ট্যাটিক টেক্সট নয়; এগুলো রিয়েল-টাইম স্টেট।
- রানটাইম সিলেক্টর প্লেসমেন্ট নির্ধারণ করার সময় ডায়নামিকালি ফিল্টার করবে:
  1. `capability_signature` কি ম্যাচ করে?
  2. প্রোভাইডারের স্ট্যাটাস কি `HEALTHY`?
  3. কোটা কি অবশিষ্ট আছে (`quota_remaining > 0`)?
  4. টাস্কের রিস্ক লেভেল কি প্রোভাইডারের পলিসি দ্বারা অনুমোদিত?

---

## ৩. Anti-Patterns & Strict Bans

| Anti-Pattern | কেন নিষিদ্ধ? | সঠিক বিকল্প |
|---|---|---|
| **Hardcoded Provider Enum** | নতুন প্রোভাইডার আসলে পাইথন কোড/এন্ট্রি মডিফাই করতে হয়। | ওপেন স্ট্রিং আইডেন্টিফায়ার বা এক্সটেনসিবল ক্যাটাগরি ফ্যামিলি। |
| **Model/Brand Names in Business Logic** | মডেলে পরিবর্তন বা ডেপ্রিকেশন হলে সার্ভিস ভেঙে পড়ে। | Capability-based routing (`task_type="reasoning"`, `capability="code.review.v1"`). |
| **Illustrative Examples as Architecture** | "যেমন: Bolt বা Lovable" কথাটিকে আর্কিটেকচারাল লিমিটেশন ধরে নেওয়া। | এগুলো শুধুই প্লাগেবল অ্যাডাপ্টারের উদাহরণ; কোর সিস্টেম কেবল $1 \dots N$ পুল চেনে। |
| **Permanent Browser Processes for Registrations** | ৪০টি সার্ভিস রেজিস্টার্ড থাকলে ৪০টি ব্রাউজার সেশন চালু রাখা। | On-Demand ব্রাউজার সেশন: কাজ আসলে তৈরি হবে, কাজ শেষে ধ্বংস হবে। |

---

## ৪. Checklist for Every Pull Request & Implementation

যেকোনো নতুন ফিচার বা কোড পরিবর্তনের ক্ষেত্রে ডেভেলপার/এজেন্টকে নিচের বিষয়গুলো যাচাই করতে হবে:

- [ ] কোডের কোনো অংশে কি কোনো নির্দিষ্ট কোম্পানি, সার্ভিস বা মডেলের নাম হার্ডকোড করা হয়েছে?
- [ ] কাল যদি নতুন একটি প্রোভাইডার/মডেল যোগ হয়, তবে কি কোর ফাইল পরিবর্তন না করেই কনফিগারেশন/রেজিস্ট্রির মাধ্যমে তা যুক্ত করা সম্ভব?
- [ ] এক্সিকিউশন রাউটিং কি Capability Signature এবং Quota/Health পলিসি অনুযায়ী কাজ করছে?
- [ ] অ্যাডাপ্টার কি সম্পূর্ণ আইসোলেটেড এবং ডায়নামিক লোডারের সাথে সামঞ্জস্যপূর্ণ?
