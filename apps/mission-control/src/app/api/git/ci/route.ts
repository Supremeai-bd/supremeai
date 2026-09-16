import { NextResponse } from "next/server";
import { getConfig } from "@/lib/github-client";

export const dynamic = "force-dynamic";

interface RunRow {
  id: number;
  name: string;
  event: string;
  status: string;
  conclusion: string | null;
  head_branch: string;
  head_sha: string;
  html_url: string;
  created_at: string;
}

export async function GET(request: Request) {
  const url = new URL(request.url);
  const limit = Math.min(Number(url.searchParams.get("limit") ?? 8) || 8, 30);
  // Dynamic by Design: token resolves DB setting → env (same chain as the rest of the Git Sync Center).
  const { token, repo } = await getConfig();

  try {
    const res = await fetch(`https://api.github.com/repos/${repo}/actions/runs?per_page=${limit}`, {
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${token}`,
        "X-GitHub-Api-Version": "2022-11-28",
      },
      cache: "no-store",
      signal: AbortSignal.timeout(25000),
    });
    if (!token)
      return NextResponse.json({ error: "GitHub token not configured — paste it in Settings → Control Tower & Repo" }, { status: 502 });
    if (!res.ok) return NextResponse.json({ error: `GitHub ${res.status}: ${res.statusText}` }, { status: 502 });
    const data = (await res.json()) as { workflow_runs?: RunRow[] };
    const runs = (data.workflow_runs ?? []).map((r) => ({
      id: r.id,
      name: r.name,
      event: r.event,
      status: r.status,
      conclusion: r.conclusion,
      branch: r.head_branch,
      sha: r.head_sha.slice(0, 7),
      url: r.html_url,
      createdAt: r.created_at,
    }));
    return NextResponse.json({ runs, repo });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
