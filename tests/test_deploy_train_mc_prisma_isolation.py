"""#4035 চুক্তি-টেস্ট: deploy-train Mission Control Prisma migration P1012 isolation।

ফরেনসিক প্রেক্ষাপট (run 37413526850 + 37409048512/37409428367/37410762583):
`mission-control-migration` job-এর `Push schema to database` step প্রতি push-এ
P1012 দিয়ে মরছিল —

    error: Error validating datasource `db`: the URL must start with the
    protocol `file:`.

কারণ: CI-র repo-wide `secrets.DATABASE_URL` হলো backend-এর Postgres URL
(Alembic/psycopg2 তাতে চলে), কিন্তু `apps/mission-control/prisma/schema.prisma`-র
datasource `provider = "sqlite"` — Prisma-র নিয়মে URL অবশ্যই `file:` হতে হবে।
Job-টির পুরনো `if [ -z "$DATABASE_URL" ]` গার্ড কখনো true হয় না (secret সেট
থাকে), তাই `prisma db push` সবসময় Postgres URL পেত → নিশ্চিত P1012।

নিরাময় (#4035): job-level isolation — step-এর env এখন
`${{ secrets.MISSION_CONTROL_DATABASE_URL || 'file:./prisma/ci-validate.db' }}` —
backend-এর Postgres URL কখনোই এই step-এ প্রবেশ করতে পারে না।

নিয়ম (repo প্যাটার্ন, #2901-এর মতো):
- Workflow চুক্তি PyYAML দিয়ে পার্স (কাঁচা টেক্সট নয় — #2862 আর্টিফ্যাক্ট-মুক্ত)।
- GitHub-expression `||` সেমান্টিক্সের সৎ সিমুলেশন — কোনো prisma-mock নয়:
  আসল চুক্তি হলো "রেজলভড URL-এর প্রোটোকল file: হলে P1012 অসম্ভব"।
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "deploy-train.yml"
MC_SCHEMA = REPO_ROOT / "apps" / "mission-control" / "prisma" / "schema.prisma"


def _mc_job() -> dict:
    graph = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
    return graph["jobs"]["mission-control-migration"]


def _push_step(job: dict) -> dict:
    for step in job["steps"]:
        if step.get("name") == "Push schema to database":
            return step
    raise AssertionError("mission-control-migration-এ 'Push schema to database' step নেই")


# ─────────────────────────────────────────────────────────────────────────────
# ১. Isolation চুক্তি — backend Postgres URL এই job-এ ঢুকতে পারবে না
# ─────────────────────────────────────────────────────────────────────────────
class TestMCPrismaIsolation:
    def test_step_never_reads_repo_wide_database_url_secret(self):
        # P1012-এর মূল কারণ ফিরে আসা নিষেধ: secrets.DATABASE_URL (Postgres)
        env_yaml = str(_push_step(_mc_job()).get("env", {}))
        assert "secrets.DATABASE_URL" not in env_yaml.replace(
            "secrets.MISSION_CONTROL_DATABASE_URL", ""
        ), "Push step আবার repo-wide secrets.DATABASE_URL পড়ছে (#4035 regression)"

    def test_step_uses_dedicated_mc_secret_with_file_fallback(self):
        env = _push_step(_mc_job())["env"]
        url_expr = env["DATABASE_URL"]
        assert "secrets.MISSION_CONTROL_DATABASE_URL" in url_expr
        assert "'file:" in url_expr, "MC-নির্দিষ্ট secret না থাকলে file: fallback লাগবেই"

    def test_no_empty_skip_guards_remain(self):
        # পুরনো দুর্বলতা: `if [ -z "$DATABASE_URL" ]; exit 0` — secret সেট থাকায়
        # কখনো ট্রিগার হতো না, আর থাকলেও নীরব-স্কিপ honest-fail নীতির বিরুদ্ধে।
        run = _push_step(_mc_job()).get("run", "")
        assert '-z "$DATABASE_URL"' not in run, "নীরব-স্কিপ গার্ড ফিরে এসেছে"
        assert "prisma db push" in run, "আসল schema-push অপসারিত হয়েছে"

    def test_job_still_non_blocking(self):
        # #3648 সিদ্ধান্ত অপরিবর্তিত: MC গৌণ সার্ভিস — ব্যর্থ হলেও deploy চলবে
        assert _mc_job().get("continue-on-error") is True


# ─────────────────────────────────────────────────────────────────────────────
# ২. Schema-পার্শ্ব অপরিবর্তনীয়তা — provider=sqlite ⇒ চুক্তির ভিত্তি
# ─────────────────────────────────────────────────────────────────────────────
class TestPrismaSchemaContract:
    def test_mc_datasource_is_sqlite(self):
        text = MC_SCHEMA.read_text(encoding="utf-8")
        m = re.search(r"datasource\s+db\s*\{(.*?)\}", text, re.DOTALL)
        assert m, "schema.prisma-এ datasource db ব্লক নেই"
        assert 'provider = "sqlite"' in m.group(1), (
            "MC provider এখন sqlite নয় — provider বদলালে #4035-এর isolation-"
            "চুক্তিও নতুন করে বিচার করতে হবে (এই টেস্ট সেই সতর্কবার্তাই)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# ৩. সিমুলেশন — CI-র আসল অবস্থায় (MC secret unset, repo-wide Postgres সেট)
#    রেজলভড URL কি সবসময় file: প্রোটোকল দেয়? (Tier-3: postgres-সেট হলেও সবুজ)
# ─────────────────────────────────────────────────────────────────────────────
class TestResolvedUrlIsAlwaysFileProtocol:
    @staticmethod
    def _resolve(expr: str, mc_secret: str) -> str:
        """GitHub `||` সেমান্টিক্সের সৎ সিমুলেশন: খালি/unset স্ট্রিং falsy।"""
        m = re.match(
            r"\$\{\{\s*secrets\.MISSION_CONTROL_DATABASE_URL\s*\|\|\s*'([^']+)'\s*\}\}",
            expr,
        )
        assert m, f"অপরিচিত expression-আকৃতি: {expr!r}"
        return mc_secret if mc_secret else m.group(1)

    def test_mc_secret_unset_resolves_to_ci_sqlite_file(self):
        # CI-র বাস্তব অবস্থা: MISSION_CONTROL_DATABASE_URL নেই, repo-wide
        # DATABASE_URL (Postgres) কল্পে সেট — তবু রেজলভড মান file: …
        expr = _push_step(_mc_job())["env"]["DATABASE_URL"]
        resolved = self._resolve(expr, mc_secret="")
        assert resolved.startswith("file:"), (
            f"MC secret unset হলে রেজলভড URL file: হতে হবে, পেলাম {resolved!r}"
        )

    def test_mc_secret_set_to_postgres_is_explicit_operator_choice(self):
        # ভবিষ্যতে remote MC DB এলে operator নিজেই postgres URL দেবেন —
        # তখন যেন সেটা সচেতন পছন্দ হয়: expression অবশ্যই ডেডিকেটেড
        # secret-কে প্রথম-পছন্দ দেবে, নীরবে ওভাররাইড হবে না।
        expr = _push_step(_mc_job())["env"]["DATABASE_URL"]
        assert expr.index("secrets.MISSION_CONTROL_DATABASE_URL") < expr.index("||")

    def test_file_fallback_survives_yaml_roundtrip(self):
        # YAML single-quote → মান literal থাকে; এবং fallback আসলেই একটি
        # বৈধ relative SQLite path (prisma CLI schema-ডিরের সাপেক্ষে)
        expr = _push_step(_mc_job())["env"]["DATABASE_URL"]
        m = re.search(r"'\s*(file:\S+?)\s*'", expr)
        assert m, "file: fallback কোটেড লিটারেল নয়"
        assert m.group(1).startswith("file:")
