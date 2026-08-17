#!/usr/bin/env python3
"""SupremeAI Security Guard — কমিটের আগে সিক্রেট শনাক্তকারী স্ক্যানার।

এই স্ক্রিপ্টটি গিট কমিট করার আগে স্টেজ করা ফাইলগুলো স্ক্যান করে হার্ডকোডেড
সিক্রেট (API Key, Deploy Hook, Service Account ইত্যাদি) খুঁজে বের করে। কোনো
সিক্রেট পাওয়া গেলে কমিট ব্লক করে দেয়, যাতে ডেভেলপার ভুল করেও ক্রেডেনশিয়াল
ফাস করতে না পারে।

ব্যবহার:
    python3 packages/scripts/security_guard.py

এটি সাধারণত pre-commit ফ্রেমওয়ার্কের মাধ্যমে (দেখুন .pre-commit-config.yaml)
চালানো হয়, অথবা `.git/hooks/pre-commit` থেকে সরাসরি কল করা যায়।
"""

import os
import re
import sys
import subprocess

# কমন সিক্রেটের জন্য রেজেক্স প্যাটার্ন
# বাংলা মন্তব্য: AUDIT-2026-08 — Render API key (rnd_...) এবং Infisical JWT token
# লিক হওয়ার পর এই প্যাটার্নগুলো শক্তিশালী করা হয়েছে। আগে rnd_[a-zA-Z0-9]{32}
# ছিল, কিন্তু আসল Render key ২৭ অক্ষরের ছিল — ফলে স্ক্যানার তা ধরতে পারেনি।
# এখন lenient কনফিগারেশন (min length 16) + JWT/generic token কভারেজ যোগ করা হলো।
SECRET_PATTERNS = {
    "OpenAI API Key": r"\b(sk-[a-zA-Z0-9]{20,}|sk-proj-[a-zA-Z0-9\-_]{16,}|sk-ant-[a-zA-Z0-9\-_]{16,})\b",
    "Render API Key": r"\b(rnd_[a-zA-Z0-9]{16,})\b",
    "Stripe Secret Key": r"(sk_(live|test)_[a-zA-Z0-9]{16,})",
    "AWS Access Key": r"\b(AKIA[0-9A-Z]{16})\b",
    "AWS Secret Access Key": r"(aws_secret_access_key\s*[=:]\s*['\"]?[a-zA-Z0-9/+=]{40})",
    "GCP Service Account": r"\"type\":\s*\"service_account\"",
    "Firebase API Key": r"\b(AIza[0-9A-Za-z\-_]{20,})\b",
    "GitHub Token": r"\b(ghp_[a-zA-Z0-9]{20,}|github_pat_[a-zA-Z0-9_]{20,})\b",
    "GitLab Token": r"\b(glpat-[a-zA-Z0-9\-_]{20,})\b",
    "Slack Token": r"\b(xox[baprs]-[a-zA-Z0-9\-]{10,})\b",
    "Generic JWT (Infisical/other)": r"\b(eyJ[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,}\.[A-Za-z0-9\-_]{10,})\b",
    "Generic Bearer Token": r"Bearer\s+[a-zA-Z0-9\-\._~+/]{20,}=*",
    "SupremeAI API Key": r"\b(sk-sup-[a-zA-Z0-9]{20,})\b",
    "Private Key Block": r"-----BEGIN (RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----",
}

# স্ক্যান থেকে বাদ দেওয়া এক্সটেনশন (বাইনারি / লক ফাইল)
SKIP_EXTENSIONS = (
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".ico",
    ".svg",
    ".woff",
    ".woff2",
    ".ttf",
)


def scan_staged_files() -> bool:
    """স্টেজ করা ফাইল স্ক্যান করে। True রিটার্ন করলে কোনো সমস্যা নেই।

    গিট রিপো না হলে বা কমান্ড ফেইল করলে True রিটার্ন করে (non-git পরিবেশে ব্রেক না করতে)।
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # গিট রিপো নয় বা git পাওয়া যায়নি — ব্লক করবে না
        return True

    files = [f for f in result.stdout.splitlines() if f and os.path.exists(f)]
    if not files:
        return True

    violations: list[str] = []

    for file_path in files:
        if file_path.endswith(SKIP_EXTENSIONS):
            continue

        # নিজের ফাইল স্কিপ — এখানে রেজেক্স প্যাটার্নগুলোই আছে, প্রকৃত সিক্রেট নয়
        if "security_guard.py" in file_path:
            continue

        # টেস্ট ফাইল বা ফোল্ডার হলে স্কিপ করি (যাতে ডামি টোকেন চেক লক না করে)
        normalized_path = file_path.replace("\\", "/")
        if "test_" in normalized_path or "/tests/" in normalized_path or "/test/" in normalized_path:
            continue

        # অটো-জেনারেটেড অডিট ডকুমেন্ট ও কোডবেস ডাম্প স্কিপ করা হচ্ছে —
        # এগুলো সোর্স কোডের প্রতিলিপি (mirror), প্রকৃত সিক্রেট নয়
        if "modular_audits/" in normalized_path or "docs/autogen/" in normalized_path:
            continue

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as fh:
                for line_no, line in enumerate(fh.readlines(), 1):
                    for name, pattern in SECRET_PATTERNS.items():
                        if re.search(pattern, line):
                            violations.append(
                                f"  - {file_path}:{line_no} -> Possible {name} detected!"
                            )
        except (OSError, UnicodeDecodeError):
            # পড়া যায়নি এমন ফাইল স্কিপ
            continue

    if violations:
        try:
            print("\n🚨 [SupremeAI Security Guard] COMMIT BLOCKED!")
        except UnicodeEncodeError:
            # কিছু উইন্ডোজ টার্মিনাল ইমোজি রেন্ডার করতে পারে না — সাধারণ টেক্সটে ফলব্যাক
            print("\n[!] [SupremeAI Security Guard] COMMIT BLOCKED!")
        print("You are trying to commit hardcoded secrets:")
        for v in violations:
            print(v)
        print("\nFix: Use environment variables or .env files instead.\n")
        return False

    return True


if __name__ == "__main__":
    if scan_staged_files():
        sys.exit(0)
    sys.exit(1)
