"""PreferenceMemory (tools/preference_memory.py) এর ইউনিট টেস্ট।

বাংলা: ইউজার প্রেফারেন্স লোড/সেভ/আপডেট ও কনটেক্সট প্রম্পট জেনারেশন কভার করা হয়েছে।
ডিস্কে লেখার জন্য টেম্প ডিরেক্টরি ব্যবহার করা হয়েছে।
"""

from __future__ import annotations

from tools.preference_memory import PreferenceMemory


def test_load_creates_default_preferences(tmp_path):
    pm = PreferenceMemory(memory_dir=str(tmp_path / "mem"))
    prefs = pm.load_user_preferences("user1")
    assert prefs["ui_theme"] == "dark"
    assert prefs["auto_deploy"] is False
    assert "react" in prefs["preferred_frameworks"]
    # বাংলা: ডিফল্ট প্রেফারেন্স ডিস্কে সেভ হয়েছে কিনা
    assert (tmp_path / "mem" / "user1.json").exists()


def test_update_preference_persists(tmp_path):
    pm = PreferenceMemory(memory_dir=str(tmp_path / "mem"))
    pm.load_user_preferences("user1")
    pm.update_preference("user1", "ui_theme", "light")
    import json

    saved = json.loads((tmp_path / "mem" / "user1.json").read_text())
    assert saved["ui_theme"] == "light"


def test_load_existing_preferences(tmp_path):
    pm = PreferenceMemory(memory_dir=str(tmp_path / "mem"))
    pm.load_user_preferences("user1")
    pm.update_preference("user1", "verbosity", "verbose")
    # বাংলা: নতুন ইনস্ট্যান্স দিয়ে লোড করলে সেভ করা ভ্যালু ফিরে আসবে
    pm2 = PreferenceMemory(memory_dir=str(tmp_path / "mem"))
    prefs = pm2.load_user_preferences("user1")
    assert prefs["verbosity"] == "verbose"


def test_generate_context_prompt_includes_frameworks(tmp_path):
    pm = PreferenceMemory(memory_dir=str(tmp_path / "mem"))
    pm.load_user_preferences("user1")
    prompt = pm.generate_context_prompt("user1")
    assert "USER PREFERENCES:" in prompt
    assert "Verbosity:" in prompt
    assert "react" in prompt
