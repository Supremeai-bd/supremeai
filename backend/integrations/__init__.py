"""SupremeAI Open-Source Integrations Layer.

এই প্যাকেজটি প্রমাণিত open-source AI পরিকাঠামো (mem0, Graphiti, browser-use, E2B)
নিয়ে SupremeAI-এর নিজস্ব আর্কিটেকচারে ব্রিজ/এডাপ্টার সরবরাহ করে।

নকশা-মূলনীতি (প্রজেক্ট কনভেনশন অনুসারে):
- প্রতিটি এডাপ্টার **feature-flag guarded** (env var) ও **optional-dependency** (importlib
  find_spec) — অর্থাৎ dependency ইনস্টল না থাকলে বা flag off থাকলে পুরো সিস্টেম স্বাভাবিক
  চলে এবং একটি zero-cost fallback পাথ ব্যবহার হয়।
- এখানে সব এন্ট্রি বাংলা মন্তব্যে রাখা হয়েছে; কোনো 3rd-party ব্র্যান্ড এক্সপোজ করা হয় না।
"""

from .e2b_adapter import E2BAdapter
from .graphiti_adapter import GraphitiMemoryAdapter
from .mem0_adapter import Mem0MemoryAdapter

__all__ = [
    "E2BAdapter",
    "GraphitiMemoryAdapter",
    "Mem0MemoryAdapter",
]
