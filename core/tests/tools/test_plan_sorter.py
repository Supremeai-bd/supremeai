"""PlanSorter (tools/plan_sorter.py) এর ইউনিট টেস্ট।

বাংলা: প্ল্যান সর্টিং লজিক কভার করা হয়েছে — ফাইল কন্টেন্টের কিওয়ার্ড অনুযায়ী
Urgent/Feature/Bug ক্যাটাগরাইজেশন এবং খালি ডিরেক্টরিতে [] রিটার্ন। টেম্প ডিরেক্টরি ব্যবহার করে আইসোলেটেড।
"""

from __future__ import annotations

from tools.plan_sorter import PlanSorter


def test_sort_empty_dir_returns_empty_categories(tmp_path):
    sorter = PlanSorter(admin_plan_dir=str(tmp_path), output_dir=str(tmp_path))
    result = sorter.sort_and_organize_plans()
    assert result == {"Urgent": [], "Feature": [], "Bug": []}


def test_sort_categorizes_urgent(tmp_path):
    (tmp_path / "plan1.md").write_text("# URGENT fix the login bug", encoding="utf-8")
    sorter = PlanSorter(admin_plan_dir=str(tmp_path), output_dir=str(tmp_path))
    result = sorter.sort_and_organize_plans()
    assert "plan1.md" in result["Urgent"]


def test_sort_categorizes_bug(tmp_path):
    (tmp_path / "plan2.md").write_text("This is a bug fix for the parser error", encoding="utf-8")
    sorter = PlanSorter(admin_plan_dir=str(tmp_path), output_dir=str(tmp_path))
    result = sorter.sort_and_organize_plans()
    assert "plan2.md" in result["Bug"]


def test_sort_categorizes_feature(tmp_path):
    (tmp_path / "plan3.md").write_text("Add a new dashboard widget", encoding="utf-8")
    sorter = PlanSorter(admin_plan_dir=str(tmp_path), output_dir=str(tmp_path))
    result = sorter.sort_and_organize_plans()
    assert "plan3.md" in result["Feature"]


def test_sort_copies_to_subfolder(tmp_path):
    # বাংলা: urgent/bug plan status_and_tracking-এ কপি হবে, feature plans_and_guides-এ
    (tmp_path / "urg.md").write_text("critical: patch security", encoding="utf-8")
    (tmp_path / "feat.md").write_text("Add oauth login feature", encoding="utf-8")
    sorter = PlanSorter(admin_plan_dir=str(tmp_path), output_dir=str(tmp_path))
    sorter.sort_and_organize_plans()
    assert (tmp_path / "status_and_tracking").is_dir()
    assert (tmp_path / "plans_and_guides").is_dir()
    copied = list((tmp_path / "status_and_tracking").glob("sorted_urgent_urg.md"))
    assert copied


def test_sort_ignores_non_md_files(tmp_path):
    (tmp_path / "notes.txt").write_text("not a plan", encoding="utf-8")
    sorter = PlanSorter(admin_plan_dir=str(tmp_path), output_dir=str(tmp_path))
    result = sorter.sort_and_organize_plans()
    assert result == {"Urgent": [], "Feature": [], "Bug": []}
