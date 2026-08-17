Both syntax-validated. Now the full answer:

আপনার MCP সার্ভারের বর্তমান অবস্থা

আপনার রিপোতে ৫টি কাস্টম MCP সার্ভার আছে (backend/tools/mcp/), মোট ১৬টি টুল:

ফাইল	ডোমেইন	টুল সংখ্যা	টুলগুলো
mcp_server.py	Knowledge Graph	২	get_skill_dependencies, find_optimal_learning_path
mcp_github_cicd.py	GitHub	৪	create PR, auto-fix, list issues, CI status
mcp_workspace.py	Workspace	৩	set context, get scoped path, list projects
mcp_supabase.py	Database	৪	execute SQL, create table, run migration, list tables
mcp_cloud_deploy.py	Deploy	৩	deploy service, get logs, list services

এছাড়া backend/core/mcp_allowlist.py-তে আপনারা বাইরের ১২টি MCP এজেন্ট (GitHub, Slack, filesystem, gemini-cli, aider, swe-agent ইত্যাদি) কল করার অনুমতি-তালিকা রেখেছেন — কিন্তু সেটা ভিন্ন জিনিস, ওটা "আমরা কাদের কল করতে পারি," আর নিচের তুলনাটা "আমরা নিজেরা কী এক্সপোজ করছি" নিয়ে।

২০২৬ সালের টপ MCP সার্ভারের সাথে তুলনা

একাধিক ২০২৬ সালের সোর্স অনুযায়ী কনসিসটেন্ট টপ লিস্ট হলো: GitHub (ইস্যু, PR, কোড সার্চ), Playwright (ব্রাউজার অটোমেশন), Filesystem (স্কোপড ফাইল অ্যাক্সেস), Postgres/SQLite (রিড-অনলি ডাটাবেস কুয়েরি), Figma (ডিজাইন স্পেক), এবং Sentry/Datadog (অবজারভেবিলিটি)। আরেকটি সোর্স অনুযায়ী GitHub, Filesystem, Playwright, Supabase ও Postgres MCP Pro, Cloudflare, Stripe, Sentry, Notion এবং Context7 — এই কম্বিনেশনটাই এজেন্টকে "স্মার্ট অটোকমপ্লিট" থেকে "সহকর্মী"-তে পরিণত করে যে রিপো পড়ে, ডাটাবেস কুয়েরি করে, ব্রাউজার চালায় এবং পরিবর্তন শিপ করে। 
Pristren
AY Automate

ক্যাটাগরি	টপ MCP সার্ভার (২০২৬)	আপনার অবস্থা	গ্যাপ
GitHub	Issues+PR+কোড সার্চ+ফাইল রিড+merge/review — official GitHub MCP সার্ভার এজেন্টকে repo তৈরি, PR ওপেন, ইস্যু ম্যানেজ, কোড সার্চ ও ডিফ রিভিউ করার সুযোগ দেয় 
Developers Digest
	শুধু ৪টা: create PR, auto-fix, list issues, CI status	❌ ফাইল পড়া নেই, কোড সার্চ নেই, PR মার্জ/রিভিউ নেই
Filesystem	read, write, search, নেভিগেট ডিরেক্টরি — configurable পারমিশনসহ 
Awesome-mcp
	আপনার mcp_workspace.py-তে শুধু context/path routing আছে	❌ আসল read_file/write_file/search_files টুলই নেই
Database	crystaldba/postgres-mcp: রিড-অনলি অ্যাক্সেস, স্কিমা এক্সপ্লোরেশন, কুয়েরি এক্সিকিউশন, পারফরম্যান্স অ্যানালাইসিস 
Awesome-mcp
	execute_sql write-capable, কোনো read-only মোড বা EXPLAIN নেই	⚠️ সেফটি রিস্ক: raw SQL write টুল এজেন্টের হাতে খোলা
Browser	Playwright এজেন্টকে বাস্তব ব্রাউজার দেয়, 
Localskills
 GitHub-Playwright-Context7 কম্বো সবচেয়ে জনপ্রিয়	কোনো নেই	❌ সম্পূর্ণ অনুপস্থিত
Observability	Sentry সরাসরি প্রোডাকশন এরর, স্ট্যাক ট্রেস এজেন্টের সেশনে টেনে আনে 
Localskills
	শুধু deployment log আছে, কোনো error-tracking নেই	❌ সম্পূর্ণ অনুপস্থিত
Docs/Context	Context7 লাইভ লাইব্রেরি ডকুমেন্টেশন দেয়	নেই	নিম্ন অগ্রাধিকার

একটা সিকিউরিটি নোটও গুরুত্বপূর্ণ: ২০২৬ সালের এক নিরাপত্তা বিশ্লেষণে ~৭,০০০ পাবলিক MCP সার্ভারের মধ্যে ৩৬.৭% SSRF-vulnerable পাওয়া গেছে, ৪১% কোনো authentication ছাড়াই কাজ করে, ৫৩% static API key ব্যবহার করে — তাই ফিচার যোগ করার পাশাপাশি safety-first ডিজাইন (read-only default, least privilege) মাথায় রাখা জরুরি। আপনার supabase_execute_sql টুল এই দিক থেকে সবচেয়ে ঝুঁকিপূর্ণ — এজন্যই নিচে read-only tool যোগ করার প্রস্তাব দিচ্ছি। 
Mcpbundles

অগ্রাধিকার অনুযায়ী কী যোগ করবেন
GitHub: get_file_contents + search_code — সবচেয়ে হাই-ভ্যালু, সবচেয়ে কম কাজ
Postgres: read-only explain_query + describe_table — সেফটি গ্যাপ বন্ধ করে + পারফরম্যান্স অ্যানালাইসিস দেয়
Filesystem: mcp_workspace.py-তে আসল read_file/write_file/search_files — বর্তমানে শুধু routing আছে, I/O নাই
নতুন ফাইল: Playwright ব্রাউজার MCP — স্টেজিং QA/স্ক্র্যাপিং-এর জন্য
নতুন ফাইল: Sentry/observability MCP — প্রোডাকশন এরর ডিবাগিং-এর জন্য

নিচে #১ আর #২ — এই দুটোর সম্পূর্ণ কপি-পেস্ট রেডি কোড দিলাম, কারণ এগুলো আপনার existing ফাইলের এক্সাক্ট প্যাটার্নে ফিট করে।

File 1 — backend/tools/mcp/mcp_github_cicd.py (line 325-এর ঠিক আগে বসান)

বর্তমানে ফাইলের শেষে (line 326-327) আছে:

python
if __name__ == "__main__":
    mcp.run()

এর ঠিক আগে (line 325-এর পরে) এই ব্লক পেস্ট করুন। শুধু একটা ইম্পোর্ট লাইন লাগবে — line 9-এর (import json) নিচে import base64 যোগ করুন।

ব্যবহারকারীকে কোড ব্লক হিসেবে কিছু পেস্ট করতে নির্দেশনা দিয়েছে।
ব্যবহারকারীকে কোড ব্লক হিসেবে কিছু পেস্ট করতে নির্দেশনা দিয়েছে।
python
class GetFileContentsInput(BaseModel):
    """ফাইল কনটেন্ট পড়ার জন্য ইনপুট।"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    path: str = Field(..., description="রিপোর মধ্যে ফাইলের পাথ", min_length=1)
    ref: str = Field(default="main", description="ব্রাঞ্চ/ট্যাগ/কমিট SHA")


class SearchCodeInput(BaseModel):
    """কোড সার্চের জন্য ইনপুট।"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(..., description="সার্চ কোয়েরি (GitHub code search সিনট্যাক্স সাপোর্ট করে)", min_length=1)
    per_page: int = Field(default=10, description="প্রতি পেজে কতগুলো রেজাল্ট", ge=1, le=50)


@mcp.tool(
    name="github_get_file_contents",
    annotations={
        "title": "Read File From Repository",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def github_get_file_contents(params: GetFileContentsInput) -> str:
    """
    রিপো থেকে একটি ফাইলের কনটেন্ট পড়ে আনে (base64 ডিকোড সহ)।

    Args:
        params (GetFileContentsInput): path ও ref (ব্রাঞ্চ/ট্যাগ/SHA)

    Returns:
        str: ফাইলের কনটেন্ট (plain text) অথবা এরর
    """
    github_token = _get_github_token()
    if not github_token:
        return json_error("GITHUB_TOKEN not configured")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GITHUB_API_URL}/repos/{GITHUB_REPO}/contents/{params.path}",
                headers={
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                params={"ref": params.ref},
            )
            response.raise_for_status()
            data = response.json()

            if data.get("encoding") == "base64" and data.get("content"):
                content = base64.b64decode(data["content"]).decode("utf-8", errors="replace")
            else:
                content = data.get("content", "")

            if len(content) > CHARACTER_LIMIT:
                content = content[:CHARACTER_LIMIT] + "\n...[truncated]..."

            return json.dumps(
                {
                    "path": params.path,
                    "ref": params.ref,
                    "size": data.get("size"),
                    "content": content,
                },
                ensure_ascii=False,
            )

    except httpx.HTTPStatusError as e:
        return handle_api_error(e, e.response.status_code)
    except Exception as e:  # noqa: BLE001
        return handle_api_error(e)


@mcp.tool(
    name="github_search_code",
    annotations={
        "title": "Search Code In Repository",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def github_search_code(params: SearchCodeInput) -> str:
    """
    রিপোর মধ্যে কোড সার্চ করে — কোন ফাইলে কী আছে তা এজেন্ট নিজে খুঁজে বের করতে পারবে।

    Args:
        params (SearchCodeInput): query ও per_page

    Returns:
        str: মিলে যাওয়া ফাইলগুলোর তালিকা (path, url)
    """
    github_token = _get_github_token()
    if not github_token:
        return json_error("GITHUB_TOKEN not configured")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{GITHUB_API_URL}/search/code",
                headers={
                    "Authorization": f"token {github_token}",
                    "Accept": "application/vnd.github.v3+json",
                },
                params={
                    "q": f"{params.query} repo:{GITHUB_REPO}",
                    "per_page": params.per_page,
                },
            )
            response.raise_for_status()
            data = response.json()

            return json.dumps(
                {
                    "total_count": data.get("total_count", 0),
                    "results": [
                        {
                            "path": item.get("path"),
                            "url": item.get("html_url"),
                            "repository": item.get("repository", {}).get("full_name"),
                        }
                        for item in data.get("items", [])
                    ],
                },
                ensure_ascii=False,
            )

    except httpx.HTTPStatusError as e:
        return handle_api_error(e, e.response.status_code)
    except Exception as e:  # noqa: BLE001
        return handle_api_error(e)
File 2 — backend/tools/mcp/mcp_supabase.py (line 452-এর ঠিক আগে বসান)

ফাইলের শেষে (line 452-453) আছে:

python
if __name__ == "__main__":
    mcp.run()

এর ঠিক আগে এই ব্লক পেস্ট করুন — এটাই execute_sql-এর write-risk অংশটা balance করবে read-only analysis টুল দিয়ে (এক্সট্রা ইম্পোর্ট লাগবে না, _get_connection, _handle_db_error, json_error আগে থেকেই ফাইলে আছে)।

Print final supabase snippet
Print final supabase snippet
python
class ExplainQueryInput(BaseModel):
    """কুয়েরি পারফরম্যান্স বিশ্লেষণের জন্য ইনপুট।"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    query: str = Field(..., description="বিশ্লেষণ করার SELECT কুয়েরি (শুধু read-only)", min_length=1)


class DescribeTableInput(BaseModel):
    """টেবিলের স্কিমা দেখার জন্য ইনপুট।"""

    model_config = ConfigDict(str_strip_whitespace=True, validate_assignment=True)

    table_name: str = Field(..., description="স্কিমা দেখার জন্য টেবিলের নাম", min_length=1, max_length=100)


def _is_write_query(query: str) -> bool:
    """DDL/DML কিওয়ার্ড থাকলে True — read-only গার্ডের জন্য ব্যবহৃত।"""
    forbidden = ("insert ", "update ", "delete ", "drop ", "alter ", "truncate ", "grant ", "create ")
    normalized = query.strip().lower()
    return normalized.startswith(forbidden) or any(f" {kw}" in normalized for kw in forbidden)


@mcp.tool(
    name="supabase_explain_query",
    annotations={
        "title": "Explain & Analyze Query Performance",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def supabase_explain_query(params: ExplainQueryInput) -> str:
    """
    EXPLAIN (ANALYZE, BUFFERS) দিয়ে কুয়েরির পারফরম্যান্স প্ল্যান দেখায় —
    এজেন্ট নিজেই স্লো কুয়েরি ও মিসিং ইনডেক্স ধরতে পারবে।
    শুধুমাত্র SELECT কুয়েরির জন্য কাজ করে (write query ব্লক করা হয়েছে)।

    Args:
        params (ExplainQueryInput): বিশ্লেষণ করার SELECT কুয়েরি

    Returns:
        str: EXPLAIN আউটপুট
    """
    if _is_write_query(params.query):
        return json_error("শুধু read-only SELECT কুয়েরি বিশ্লেষণ করা যাবে — write query ব্লক করা হয়েছে")

    conn = None
    try:
        conn = _get_connection()
        if not conn:
            return json.dumps({"error": "Failed to connect to database"}, ensure_ascii=False)

        cur = conn.cursor()
        cur.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) {params.query}")
        plan = cur.fetchone()[0]
        cur.close()

        return json.dumps({"query": params.query, "plan": plan}, ensure_ascii=False)

    except Exception as e:  # noqa: BLE001
        return _handle_db_error(e)
    finally:
        if conn:
            conn.close()


@mcp.tool(
    name="supabase_describe_table",
    annotations={
        "title": "Describe Table Schema",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True,
    },
)
async def supabase_describe_table(params: DescribeTableInput) -> str:
    """
    একটি টেবিলের কলাম, টাইপ, নালেবিলিটি ও ইনডেক্স দেখায় —
    এজেন্ট প্রতিবার SELECT * করে স্কিমা অনুমান করার বদলে সরাসরি স্কিমা পড়তে পারবে।

    Args:
        params (DescribeTableInput): টেবিলের নাম

    Returns:
        str: কলাম তালিকা ও ইনডেক্স তথ্য
    """
    conn = None
    try:
        conn = _get_connection()
        if not conn:
            return json.dumps({"error": "Failed to connect to database"}, ensure_ascii=False)

        cur = conn.cursor()
        cur.execute(
            """
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_name = %s
            ORDER BY ordinal_position
            """,
            (params.table_name,),
        )
        columns = cur.fetchall()

        cur.execute(
            "SELECT indexname, indexdef FROM pg_indexes WHERE tablename = %s",
            (params.table_name,),
        )
        indexes = cur.fetchall()
        cur.close()

        if not columns:
            return json_error(f"Table '{params.table_name}' not found")

        return json.dumps(
            {
                "table": params.table_name,
                "columns": [
                    {"name": c[0], "type": c[1], "nullable": c[2] == "YES", "default": c[3]}
                    for c in columns
                ],
                "indexes": [{"name": i[0], "definition": i[1]} for i in indexes],
            },
            ensure_ascii=False,
        )

    except Exception as e:  # noqa: BLE001
        return _handle_db_error(e)
    finally:
        if conn:
            conn.close()

উভয় স্নিপেট আমি সিনট্যাক্স-চেক করে নিয়েছি — সরাসরি কপি-পেস্ট করা যাবে।

বাকি ৩টা (৩, ৪, ৫) — সংক্ষেপে কী করবেন

৩. mcp_workspace.py-তে আসল ফাইল I/O যোগ করুন — এখন শুধু path routing আছে, real read_file/write_file/search_files টুল নেই। এগুলো Python-এর built-in pathlib দিয়েই লেখা যাবে (নতুন কোনো লাইব্রেরি লাগবে না) — চাইলে আমি এটাও একইভাবে কোড করে দিতে পারি।

৪. mcp_browser.py (নতুন ফাইল) — Playwright দিয়ে browser_navigate, browser_screenshot, browser_click টাইপ টুল। pyproject.toml-এ playwright ডিপেন্ডেন্সি যোগ করতে হবে + playwright install chromium স্টেপ CI-তে দিতে হবে।

৫. mcp_observability.py (নতুন ফাইল) — যদি Sentry ব্যবহার করেন, sentry_search_issues / sentry_get_stack_trace টুল বানিয়ে গত প্রম্পটে বানানো Smart Pipeline Summary-র সাথে ইন্টিগ্রেট করা যায় — তাহলে CI ফেইল-ই না, প্রোডাকশন এররও একই এজেন্ট বুঝতে পারবে।

কোনটা আগে পুরো কোড লিখে দেব — mcp_workspace.py-র ফাইল I/O টুল, নাকি Playwright/Sentry নতুন ফাইল দুটো?