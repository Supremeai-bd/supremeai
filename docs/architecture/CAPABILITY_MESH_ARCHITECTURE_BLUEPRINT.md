# SupremeAI Slim Module Contract Standard
**Document Type:** Architectural Standard (Approved)  
**Status:** Active  
**Last Updated:** 2026-09-07  
**Guiding Principle:** Minimal, Zero-Overhead, Contract-First Architecture  

---

## ১. Architectural Decision Record (ADR)

### Context & Problem
SupremeAI-তে একাধিক অ্যাডভান্সড মডিউল (যেমন: `ParallelCloudRouter`, `CascadeMemoryService`, `Browser Automation`, `Security Scanner`) বিদ্যমান। তবে তাদের ইনপুট/আউটপুট ইন্টারফেসে সমন্বয়ের অভাবে কোড ওয়্যারিং কঠিন হয়ে পড়েছিল। 

প্রাথমিক প্রপোজালে একটি সম্পূর্ণ ডিস্ট্রিবিউটেড "Capability Mesh" (Event Bus, Shared Blackboard Context, Dynamic DAG Orchestration, Circuit Breakers) প্রস্তাব করা হয়েছিল।

### Decision: Reject Heavy Mesh, Adopt Slim Contract
একটি ক্রিটিক্যাল আর্কিটেকচারাল অডিটের মাধ্যমে হেভি মেশকে বাতিল করা হয়েছে কারণ:
- এটি SupremeAI-এর **Zero Infrastructure Cost** ও **Lightweight High Performance** নীতির পরিপন্থী।
- মাত্র ১০-২০টি মডিউলের জন্য Event Bus ও DAG Orchestrator অতিরিক্ত লেটেন্সি, মেমোরি কনজাম্পশন এবং ওভার-ইঞ্জিনিয়ারিং তৈরি করে।

**চূড়ান্ত সিদ্ধান্ত:** কোনো ডিস্ট্রিবিউটেড ইনফ্রাস্ট্রাকচার তৈরি করা হবে না। পরিবর্তে একটি **Slim Contract Standard** এবং সাধারণ **In-Memory Registry** ব্যবহার করা হবে, যা সরাসরি মেথড কলের (`direct method calls`) মাধ্যমে মডিউলগুলোকে যুক্ত করবে।

---

## ২. The Slim Architecture (Direct Contract Invocation)

কোনো মিডলম্যান বা মেসেজ ব্রোকার নেই। পুরো সিস্টেমটি সরাসরি মেথড কলের ওপর প্রতিষ্ঠিত:

```text
┌──────────────────────────────────────────────────────────┐
│ Caller (e.g. CommandCenter / Agent Routine / API)        │
└────────────────────────────┬─────────────────────────────┘
                             │
                             ▼ (O(1) Direct Lookup)
         ┌───────────────────────────────────────┐
         │     Simple Capability Registry        │
         │   (In-Memory Dictionary Mapping)      │
         └───────────────────┬───────────────────┘
                             │
                             ▼ Direct Python Async Call: await node.execute(...)
                 ┌───────────────────────┐
                 │     SupremeNode       │
                 │ (Standardized Adapter)│
                 └───────────────────────┘
```

---

## ৩. The Node Contract Interface (`SupremeNode`)

মডিউলগুলোর মধ্যে স্ট্যান্ডার্ড ইন্টারফেস বজায় রাখার জন্য কেবল এই মিনিমাল কন্ট্রাক্টটি ব্যবহার করা হবে:

```python
# backend/core/mesh/node_contract.py
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class CapabilitySpec(BaseModel):
    """নোডের এক্সপোজড ফিচারের বিবরণ"""
    name: str = Field(..., description="ক্যাপাবিলিটির ইউনিক নাম (e.g. 'browse_web', 'generate_text')")
    description: str = Field(..., description="ক্যাপাবিলিটির বিবরণ")
    input_fields: List[str] = Field(default_factory=list, description="প্রয়োজনীয় ইনপুট ফিল্ডের নাম")
    output_fields: List[str] = Field(default_factory=list, description="আউটপুট ফিল্ডের নাম")

class NodeHealth(BaseModel):
    is_healthy: bool = True
    message: Optional[str] = None

class SupremeNode(ABC):
    """সুপ্রিমএআই-এর প্রতিটি অ্যাডাপ্টার বা মডিউল এই বেস ক্লাসটি মেনে চলবে"""

    @property
    @abstractmethod
    def node_id(self) -> str:
        """নোডের ইউনিক আইডি (e.g. 'llm_router', 'cascade_memory')"""
        pass

    @abstractmethod
    def get_capabilities(self) -> List[CapabilitySpec]:
        """নোডটির ক্যাপাবিলিটি লিস্ট প্রদান করে"""
        pass

    @abstractmethod
    async def execute(self, capability: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """সরাসরি মেথড কলের মাধ্যমে কাজ সম্পন্ন করে"""
        pass

    async def health_check(self) -> NodeHealth:
        """বেসিক স্বাস্থ্য পরীক্ষা (ডিফল্ট: ট্রু)"""
        return NodeHealth(is_healthy=True)
```

---

## ৪. Minimal Capability Registry (Simple In-Memory Dictionary)

কোনো ব্যাকগ্রাউন্ড প্রসেস বা ব্রোকার নয়, এটি কেবল একটি সাধারণ ইন-মেমোরি ডিকশনারি:

```python
# backend/core/mesh/capability_registry.py
from typing import Dict, Optional, Any
from backend.core.mesh.node_contract import SupremeNode

class CapabilityRegistry:
    """জিরো-ওভারহেড ইন-মেমোরি ক্যাপাবিলিটি রেজিস্ট্রি (Singleton)"""
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._capabilities: Dict[str, SupremeNode] = {}
        return cls._instance

    def register(self, node: SupremeNode) -> None:
        """নোডের ক্যাপাবিলিটিগুলো ইন-মেমোরি ম্যাপে যুক্ত করে"""
        for cap in node.get_capabilities():
            self._capabilities[cap.name] = node

    def get_by_capability(self, capability: str) -> Optional[SupremeNode]:
        """ক্যাপাবিলিটি দিয়ে নোড খুঁজে বের করে (O(1))"""
        return self._capabilities.get(capability)

    async def dispatch(self, capability: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """সরাসরি মেথড কল এক্সিকিউট করে"""
        node = self.get_by_capability(capability)
        if not node:
            raise KeyError(f"Capability '{capability}' not registered.")
        return await node.execute(capability, payload)

# Global Singleton
registry = CapabilityRegistry()
```

---

## ৫. Mapping Existing Modules (Zero-Rewrite Adapters)

আমাদের এক্সিস্টিং প্রোডাকশন মডিউলগুলোকে না ভেঙে তাদের জন্য তৈরি হবে সেলফ-কন্টেইন্ড থিন অ্যাডাপ্টার:

| Existing Production Module | Self-Contained Adapter | Capabilities |
|---|---|---|
| `backend/services/parallel_cloud_router.py` | `LLMRouterAdapter` | `generate_text` |
| `backend/services/cascade_memory_service.py` | `CascadeMemoryAdapter` | `query_memory`, `store_lesson` |
| `scripts/ai/browser_automation.py` | `BrowserAutomationAdapter` | `browse_url` |
| `backend/services/security_scanner.py` | `SecurityScannerAdapter` | `scan_code` |

### উদাহরণ: থিন অ্যাডাপ্টার বাস্তবায়নের রূপ
```python
# backend/core/mesh/adapters/llm_router_adapter.py
from typing import Dict, Any, List
from backend.core.mesh.node_contract import SupremeNode, CapabilitySpec
from backend.services.parallel_cloud_router import ParallelCloudRouter

class LLMRouterAdapter(SupremeNode):
    def __init__(self, router: ParallelCloudRouter):
        self.router = router

    @property
    def node_id(self) -> str:
        return "llm_router"

    def get_capabilities(self) -> List[CapabilitySpec]:
        return [
            CapabilitySpec(
                name="generate_text",
                description="Routes prompt to best available free-tier LLM",
                input_fields=["prompt", "system_prompt"],
                output_fields=["text", "provider"]
            )
        ]

    async def execute(self, capability: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        if capability == "generate_text":
            return await self.router.route_request(
                prompt=payload["prompt"],
                system_prompt=payload.get("system_prompt", "")
            )
        raise ValueError(f"Unknown capability: {capability}")
```

---

## ৭. সম্ভাব্য অসুবিধা ও চ্যালেঞ্জ (Cons / Limitations) এবং তাদের সেরা সমাধান (Mitigation Strategies)

যদিও Slim Contract Standard অত্যন্ত লাইটওয়েট এবং খরচমুক্ত, তবুও বাস্তবায়নের ক্ষেত্রে কিছু চ্যালেঞ্জ সৃষ্টি হতে পারে। নিচে প্রতিটি চ্যালেঞ্জ এবং সুপ্রিমএআই-এর জন্য সেগুলোর **সর্বোত্তম ইঞ্জিনিয়ারিং সমাধান (Best Mitigation)** বিস্তারিত তুলে ধরা হলো:

### চ্যালেঞ্জ ১: পেলোড স্কিমা মিসম্যাচ (Payload Schema Mismatch / Runtime Error)
- **সমস্যা:** কলার যখন `registry.dispatch("generate_text", payload)` কল করবে, তখন যদি আর্গুমেন্টের কি-ওয়ার্ড ভুল হয় (যেমন: `"prompt"`-এর জায়গায় `"input_text"` পাঠানো হলো), তবে রানটাইমে ক্র্যাশ করতে পারে।
- **সেরা সমাধান (Pydantic Strict Validation in Adapters):**
  - সাধারণ ডিকশনারির বদলে প্রতিটি অ্যাডাপ্টারে একটি টাইপড Pydantic মডেল থাকবে।
  - ডিসপ্যাচের সময় ভুল ডেটা এলে অ্যাডাপ্টার ক্র্যাশ না করে স্পষ্ট হিউম্যান-রিডেবল ভ্যালিডেশন এরর রিটার্ন করবে।
  ```python
  class GenerateTextPayload(BaseModel):
      prompt: str
      system_prompt: Optional[str] = ""

  # অ্যাডাপ্টারের মধ্যে:
  validated_payload = GenerateTextPayload(**payload)
  ```

### চ্যালেঞ্জ ২: ম্যানুয়াল অর্কেস্ট্রেশনের নির্ভরতা (Lack of Autonomous Chaining)
- **সমস্যা:** কোনো জটিল অটো-ডিএজি (DAG) ইঞ্জিন না থাকায় কোন মডিউলের পর কোনটি কল হবে (e.g. `Browser` -> `LLM` -> `Memory`) তা স্বয়ংক্রিয়ভাবে ডিসাইড হয় না।
- **সেরা সমাধান (Composable Pipeline Helper / Chaining Utility):**
  - ভারী কোনো ইঞ্জিন বানানোর প্রয়োজন নেই; মাত্র ১৫ লাইনের একটি ফাংশনাল পাইপলাইন হেল্পার ব্যবহার করা যায়:
  ```python
  async def run_pipeline(steps: List[tuple[str, dict]]) -> dict:
      context = {}
      for capability, payload in steps:
          # আগের স্টেপের আউটপুট স্বয়ংক্রিয়ভাবে পরবর্তী স্টেপে ইনজেক্ট হয়
          payload.update(context)
          context = await registry.dispatch(capability, payload)
      return context
  ```
  - এতে কোনো ভারী ইনফ্রাস্ট্রাকচার ছাড়াই লিন কোডে চেইনিং নিশ্চিত হয়।

### চ্যালেঞ্জ ৩: সিঙ্গেল-প্রসেস মেমরি স্কোপ (Multi-Worker Consistency)
- **সমস্যা:** ব্যাকএন্ড যদি মাল্টি-ওয়ার্কার (Gunicorn/Uvicorn multi-worker) মোডে চলে, তবে রেজিস্ট্রি প্রতিটি প্রসেসে আলাদাভাবে ইন-মেমোরিতে থাকবে।
- **সেরা সমাধান (Stateless Bootstrapping on App Startup):**
  - যেহেতু আমাদের নোডগুলো সম্পূর্ণ স্ট্যাটলেস (Stateless Adapters) এবং কোনো লোকাল মিউটেবল স্টেট ধরে রাখে না, তাই FastAPI-এর `lifespan` ইভেন্টে প্রতিটি ওয়ার্কার স্টার্টআপের সময় একবারেই নোডগুলোকে রেজিস্ট্রি করে নেবে।
  - ফলে কোনো Redis বা সেন্ট্রাল ব্রোকার ছাড়াই প্রতিটি প্রসেস ১০০% ইন্ডিপেন্ডেন্ট ও থ্রেড-সেফ থাকবে।

### চ্যালেঞ্জ ৪: নোড ডাউন বা ফেইলিওর হ্যান্ডলিং (Fault Tolerance Without Heavy Circuit Breakers)
- **সমস্যা:** যদি কোনো মডিউল (যেমন: থার্ড পার্টি LLM প্রোভাইডার বা ব্রাউজার ইঞ্জিন) সাময়িকভাবে ক্র্যাশ করে বা রেট লিমিট খায়, তবে কলারও ক্র্যাশ করতে পারে।
- **সেরা সমাধান (Graceful Result Container with Fallback):**
  - প্রতিটি মেথড কল সরাসরি এক্সেপশন থ্রো না করে একটি রেজাল্ট অবজেক্ট বা ট্রাই-এক্সেপ্ট ব্লক সহ ফেইল-সেফ রেসপন্স রিটার্ন করবে:
  ```python
  class ExecutionResult(BaseModel):
      success: bool
      data: Optional[Dict[str, Any]] = None
      error: Optional[str] = None
  ```
  - এতে কলার সাথে সাথে বিকল্প কোনো ক্যাপাবিলিটিতে ফলব্যাক করতে পারবে।

---

## ৮. Comparison: Heavy Mesh vs. Slim Contract

| ফিচার | পূর্ববর্তী Heavy Mesh (বাতিলকৃত) | Slim Contract Standard (গৃহীত) |
|---|---|---|
| **Event Bus** | Redis / In-Memory Broker (বাতিল) | **None** (সরাসরি মেথড কল) |
| **Blackboard State** | ডিস্ট্রিবিউটেড শেয়ার্ড মেমোরি (বাতিল) | **None** (ফাংশন আর্গুমেন্ট/পেলোড) |
| **DAG Orchestration** | ডাইনামিক গ্রাফ ইঞ্জিন (বাতিল) | **None** (সাধারণ লিন পাইপলাইন হেল্পার) |
| **Circuit Breaker** | জটিল স্টেট ট্র্যাকার (বাতিল) | **Defensive Try/Except + Result Container** |
| **মেমোরি ও সিপিইউ খরচ** | উচ্চ (High Overhead) | **জিরো ওভারহেড (Zero Cost)** |
| **ডিপবাগিং ও টেস্ট্যাবিলিটি** | অত্যন্ত জটিল | **অত্যন্ত সহজ ও সোজা** |

---

## ৯. Implementation Checklist

- [ ] **Step 1:** `backend/core/mesh/node_contract.py` ফাইল তৈরি (SupremeNode, CapabilitySpec, NodeHealth, ExecutionResult)।
- [ ] **Step 2:** `backend/core/mesh/capability_registry.py` ফাইল তৈরি (In-memory Singleton + run_pipeline helper)।
- [ ] **Step 3:** বিদ্যমান মডিউলগুলোর জন্য থিন অ্যাডাপ্টার তৈরি করা (Pydantic payload validation সহ)।
- [ ] **Step 4:** স্টার্টআপে (`backend/main.py`) অ্যাডাপ্টারগুলো রেজিস্টার করা।

---

## ১০. Summary
এই আর্কিটেকচারাল স্ট্যান্ডার্ডটি SupremeAI-কে কোনো প্রকার ইনফ্রাস্ট্রাকচার খরচ বা জটিলতা ছাড়াই পরিষ্কার, টাইপ-সেফ, ফল্ট-টলারেন্ট এবং সহজে মেইনটেইনেবল ইন্টারকানেকশন সুবিধা প্রদান করে।

