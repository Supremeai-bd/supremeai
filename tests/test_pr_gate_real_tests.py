# বাংলা মন্তব্য: PR Gate-এর আসল কোড-টেস্ট গার্ড পুনরুদ্ধারের স্থায়ী পিন-টেস্ট (#2421 seq:1)।
# PR সরলীকরণ (#2416)-এ pr.yml-এর tests job hollow হয়ে গিয়েছিল — শুধু constitution
# self-test ও silent-exception invariant চলত; ভাঙা backend/frontend কোড PR গেট
# পার হয়ে main-এ ঢুকে যেত। এই টেস্টগুলো workflow-এর চুক্তি পিন করে — ভবিষ্যতে
# গার্ড সরালে CI-তেই ধরা পড়বে।

from pathlib import Path

import yaml

WORKFLOW = Path(".github/workflows/pr.yml")


def _tests_job() -> dict:
    data = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    job = data["jobs"]["tests"]
    assert isinstance(job, dict), "pr.yml-এ tests job নেই"
    return job


def _step_names() -> list[str]:
    # বাংলা মন্তব্য: প্রতিটি step-এর name — গার্ড-স্টেপ উপস্থিতির প্রাথমিক প্রমাণ।
    return [(s.get("name") or "") for s in _tests_job()["steps"]]


def test_backend_targeted_pytest_guard_present() -> None:
    # বাংলা মন্তব্য: detect_changed_tests.py দিয়ে টার্গেট নির্বাচন + poetry pytest —
    # হলো আসল ব্যাকএন্ড কোড টেস্ট চুক্তি।
    names = _step_names()
    assert any("Select backend test targets" in n for n in names)
    assert any("Real backend code tests" in n for n in names)
    job_yaml = yaml.safe_dump(_tests_job(), allow_unicode=True)
    assert "detect_changed_tests.py" in job_yaml, "test-target selector অনুপস্থিত"
    assert "poetry run pytest" in job_yaml, "poetry pytest রানার অনুপস্থিত"


def test_ruff_incremental_guard_present() -> None:
    # বাংলা মন্তব্য: ruff incremental (changed .py) — পুরনো pre-existing noise
    # PR মিথ্যা লাল করবে না, কিন্তু নতুন ভাঙা ফাইল ধরবে।
    job_yaml = yaml.safe_dump(_tests_job(), allow_unicode=True)
    assert "ruff check" in job_yaml, "ruff গার্ড অনুপস্থিত"
    assert "merge-base" in job_yaml, "incremental diff লজিক অনুপস্থিত"


def test_frontend_typecheck_and_build_guard_present() -> None:
    # বাংলা মন্তব্য: frontend/** বদলালে tsc typecheck ও vite build — দুটোই আবশ্যক।
    job_yaml = yaml.safe_dump(_tests_job(), allow_unicode=True)
    assert "tsc -p tsconfig.app.json --noEmit" in job_yaml, "typecheck গার্ড অনুপস্থিত"
    assert "pnpm run build" in job_yaml, "build গার্ড অনুপস্থিত"
    assert "frontend/dist" in job_yaml, "build আউটপুট যাচাই অনুপস্থিত"


def test_legacy_suites_not_weakened() -> None:
    # বাংলা মন্তব্য: পুরনো দুই সুইট (constitution self-test + silent-exception)
    # অক্ষত থাকতে হবে — নতুন গার্ড যোগ হয়েছে, কিছু সরানো হয়নি (Test Guard চুক্তি)।
    names = _step_names()
    assert any("Constitution & Gates Self-Test" in n for n in names)
    assert any("Silent Exception Swallows" in n for n in names)


def test_guards_are_path_filtered() -> None:
    # বাংলা মন্তব্য: merge-base path-filter চুক্তি — docs-only PR দ্রুত পাস,
    # backend/frontend পরিবর্তনে সংশ্লিষ্ট গার্ড বাধ্যতামূলক।
    # (YAML dump-এ কোটিং স্টাইল বদলায় তাই regex-বডি substring হিসেবে যাচাই।)
    job_yaml = yaml.safe_dump(_tests_job(), allow_unicode=True)
    assert "backend/|tests/" in job_yaml, "backend path-filter অনুপস্থিত"
    assert "^frontend/" in job_yaml, "frontend path-filter অনুপস্থিত"
