"""SupremeAI Open-Source Integrations Layer.

# বাংলা (#4057): mem0, E2B, Graphiti, Browser Use, OpenHands adapter-সমূহ
# অবসর নিয়েছে (RETIRE + DELETE) — সবই zero live caller ছিল এবং native
# capability দ্বারা প্রতিস্থাপিত। বিস্তারিত: docs/architecture/retired_adapters.md
#
# নকশা-মূলনীতি (ঐতিহাসিক রেফারেন্স):
- প্রতিটি পূর্ব-adapter feature-flag guarded + optional-dependency ছিল —
- dependency ইনস্টল না থাকলে বা flag off থাকলে zero-cost fallback পাথ ব্যবহার হতো।
- এখন সব adapter অবসর নিয়েছে — এই প্যাকেজ খালি (নতুন integration যোগ হলে
- এখানে import যোগ করতে হবে)।
"""

__all__: list[str] = []
