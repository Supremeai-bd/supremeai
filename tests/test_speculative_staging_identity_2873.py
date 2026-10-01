"""চুক্তি-টেস্ট (#2873): smart_priority_merger.SpeculativeStagingRunner — git committer identity চুক্তি।

বাংলা নোট: SpeculativeStagingRunner.run() detached worktree-তে `--no-ff` merge commit
তৈরি করে; GitHub Actions runner-এর fresh clone-এ user.name/user.email কনফিগার না থাকায়
"fatal: empty ident name" — স্টেজিং ধাপে পৌঁছানো প্রতিটি PR deterministic-ভাবে ব্যর্থ
(Train Gate run 2026-10-01T14:42:44Z, PR #2872-এর মন্তব্য 14:43:56Z-এ প্রমাণিত)।
চুক্তি: merge কমান্ডে one-shot `git -c user.name=... -c user.email=...` flags থাকতে হবে
(pure plan + run()-এর executed command — উভয়স্থানে), যাতে runner-env যা-ই হোক,
ভার্চুয়াল merge কমিট identity-নিরপেক্ষভাবে সফল হয়।
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ci" / "smart_priority_merger.py"
_spec = importlib.util.spec_from_file_location("spm_2873", SCRIPT)
spm = importlib.util.module_from_spec(_spec)
sys.modules[_spec.name] = spm  # dataclass প্রসেসিং sys.modules-এ module চায় (py3.12)
_spec.loader.exec_module(spm)

IDENT_NAME = "supremeai-coder-1-bot"
IDENT_EMAIL = "coder-1@supremeai.bot"


# ── টেস্ট ১: pure plan — build_worktree_commands() merge-কমান্ডে identity flags ──

def test_worktree_plan_merge_has_identity_flags():
    cmds = spm.SpeculativeStagingRunner.build_worktree_commands("some-head")
    merge_cmd = cmds[-1]
    assert merge_cmd[0] == "git" and "merge" in merge_cmd
    assert f"user.name={IDENT_NAME}" in merge_cmd, f"plan-এ user.name নেই: {merge_cmd}"
    assert f"user.email={IDENT_EMAIL}" in merge_cmd, f"plan-এ user.email নেই: {merge_cmd}"
    # -c flags অবশ্যই subcommand-এর আগে থাকবে (git global-opts আইন)
    assert merge_cmd.index(f"user.name={IDENT_NAME}") < merge_cmd.index("merge")


# ── টেস্ট ২: run()-এর executed merge-কমান্ডেও identity flags (wiring প্রমাণ) ──

def test_run_executed_merge_command_has_identity_flags():
    captured = []

    def fake_run_cmd(args, **_kw):
        captured.append(list(args))
        return 0, "ok", ""

    with patch.object(spm, "run_cmd", side_effect=fake_run_cmd), \
         tempfile.TemporaryDirectory() as td:
        ok, report = spm.SpeculativeStagingRunner.run("some-head", wt_path=str(Path(td) / "wt"))
    assert ok, f"run() সবুজ হওয়াই চাই (mocked I/O), পেলাম: {report}"
    merge_calls = [c for c in captured if "merge" in c]
    assert merge_calls, f"run() merge কমান্ড চালায়নি: {captured}"
    merge_cmd = merge_calls[-1]
    assert f"user.name={IDENT_NAME}" in merge_cmd, f"run()-এ user.name নেই: {merge_cmd}"
    assert f"user.email={IDENT_EMAIL}" in merge_cmd, f"run()-এ user.email নেই: {merge_cmd}"


# ── টেস্ট ৩: বাস্তব git প্রমাণ — identity-হীন env-এ flags ছাড়া merge ব্যর্থ, flags-সহ সফল ──

def _git(env, *args, cwd):
    r = subprocess.run(["git", *args], cwd=cwd, env=env, capture_output=True, text=True, check=False)
    return r.returncode, r.stdout, r.stderr


def _isolated_git_env(tmp: Path) -> dict:
    """runner-অনুরূপ identity-হীন git env: HOME বদল + system/global config বন্ধ।"""
    env = dict(os.environ)
    env["HOME"] = str(tmp)          # কোনো global git identity নেই
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env.pop("GIT_AUTHOR_NAME", None); env.pop("GIT_AUTHOR_EMAIL", None)
    env.pop("GIT_COMMITTER_NAME", None); env.pop("GIT_COMMITTER_EMAIL", None)
    return env


def test_real_git_no_ff_merge_requires_identity_and_flags_fix_it(tmp_path):
    env = _isolated_git_env(tmp_path)

    # base repo (origin ভূমিকা) — setup-কমিটে নিজের identity -c দিয়ে সেট করা
    base = tmp_path / "base.git"; base.mkdir()
    assert _git(env, "init", "-q", "--bare", "-b", "main", str(base), cwd=str(tmp_path))[0] == 0
    seed = tmp_path / "seed"; seed.mkdir()
    assert _git(env, "init", "-q", "-b", "main", str(seed), cwd=str(tmp_path))[0] == 0
    (seed / "a.txt").write_text("base\n")
    _git(env, "add", "a.txt", cwd=str(seed))
    ident_setup = ["-c", f"user.name={IDENT_NAME}", "-c", f"user.email={IDENT_EMAIL}"]
    assert _git(env, *ident_setup, "commit", "-qm", "base", cwd=str(seed))[0] == 0
    assert _git(env, "push", "-q", str(base), "main", cwd=str(seed))[0] == 0

    # head clone — দ্বিতীয় কমিট (identity আবার -c)
    head = tmp_path / "head"; head.mkdir()
    assert _git(env, "clone", "-q", str(base), str(head), cwd=str(tmp_path))[0] == 0
    assert _git(env, "checkout", "-q", "-b", "feature", "origin/main", cwd=str(head))[0] == 0
    (head / "b.txt").write_text("feat\n")
    _git(env, "add", "b.txt", cwd=str(head))
    assert _git(env, *ident_setup, "commit", "-qm", "feat", cwd=str(head))[0] == 0
    assert _git(env, "push", "-q", str(base), "feature", cwd=str(head))[0] == 0
    head_sha = _git(env, "rev-parse", "HEAD", cwd=str(head))[1].strip()

    # base-এ প্রতিদ্বন্দ্বী-বিহীন নতুন কমিট (merge commit আসতে বাধ্য করতে main এগিয়ে দেওয়া)
    (seed / "c.txt").write_text("main-move\n")
    _git(env, "add", "c.txt", cwd=str(seed))
    assert _git(env, *ident_setup, "commit", "-qm", "main-move", cwd=str(seed))[0] == 0
    assert _git(env, "push", "-q", str(base), "main", cwd=str(seed))[0] == 0

    # base-এর detached worktree-অনুরূপ clone যেখানে merge হবে — identity কোথাও নেই
    stage = tmp_path / "stage"; stage.mkdir()
    assert _git(env, "clone", "-q", "-b", "main", str(base), str(stage), cwd=str(tmp_path))[0] == 0
    assert _git(env, "fetch", "-q", str(base), "feature", cwd=str(stage))[0] == 0

    # নিয়ন্ত্রণ: flags ছাড়া --no-ff merge → runner-এর মতোই ব্যর্থ (empty ident)
    code, _, err = _git(env, "merge", "--no-ff", "--no-edit", head_sha, cwd=str(stage))
    assert code != 0, "identity ছাড়া merge ব্যর্থ হওয়াই চাই (বাগ-প্রমাণ)"
    assert ("ident" in (err or "").lower()) or ("who you are" in (err or "").lower()), \
        f"empty-ident ব্যর্থতা দাবী: {err[:200]}"

    # ফিক্স: -c one-shot flags → একই merge সফল
    code, _, err = _git(
        env, "-c", f"user.name={IDENT_NAME}", "-c", f"user.email={IDENT_EMAIL}",
        "merge", "--no-ff", "--no-edit", head_sha, cwd=str(stage),
    )
    assert code == 0, f"identity-flags দিয়ে merge সফল হওয়াই চাই: {err[:200]}"
    assert _git(env, "rev-parse", "--verify", "HEAD^2", cwd=str(stage))[0] == 0, \
        "merge commit (দ্বিতীয় parent) তৈরি হয়নি — --no-ff আইন ভাঙা"
