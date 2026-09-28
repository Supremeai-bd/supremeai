# -*- coding: utf-8 -*-
"""SupremeAI Toolkit — ইউনিফায়েড স্ক্রিপ্ট টুলচেইন (group:foundation-closeout #2403).

# বাংলা মন্তব্য: এই প্যাকেজটি রিপোজিটরির বিচ্ছিন্ন ৩৯০+ স্ক্রিপ্টকে একটি মডুলার,
# বুদ্ধিমান সেন্ট্রাল টুলে সমন্বিত করার ফাউন্ডেশন (seq:1)। Golden Rule:
# "Clean up-এর আগে Reusability Check — beneficial কিছু কোনো অবস্থাতেই ডিলিট করা যাবে না।"
# তাই প্রথম ক্ষমতা = Reusability Audit (প্রমাণ-ভিত্তিক verdict, কখনোই স্বয়ংক্রিয় ডিলিট নয়)।
# seq:2 ক্ষমতা: Harvest Engine (ছাঁটাই-প্রার্থীদের গভীর রায়) + Plan Guard (duplicate-plan স্ক্যান —
# scan_duplicate_plans.py-এর পোর্টেবল উত্তরাধিকার)।

Usage:
    python scripts/supremeai_toolkit/cli.py --help
    python -m supremeai_toolkit audit --path scripts --out report.md   # (scripts/ থেকে)
"""

__version__ = "0.2.0"
__all__ = ["cli", "reusability_audit", "harvest", "plan_guard"]
