import { db } from "@/lib/db";

/**
 * GitHub client for the Git Sync Center.
 * Implements the standing directive:
 *  - Always check PR vs main for conflicts
 *  - If main moved ahead and PR is still open → sync main into the PR branch
 *  - Keep a durable log of every check (GitSyncCheck table)
 */

const API = "https://api.github.com";

export async function getConfig(): Promise<{ token: string; repo: string }> {
  let token = process.env.GITHUB_TOKEN || "";
  let repo = process.env.GITHUB_REPO || "SaifulHaqueNiloy/supremeai";
  try {
    const rows = await db.setting.findMany({ where: { key: { in: ["githubToken", "githubRepo", "watchBranch"] } } });
    for (const r of rows) {
      if (r.key === "githubToken" && r.value) token = r.value;
      if (r.key === "githubRepo" && r.value) repo = r.value;
    }
  } catch (err) {
    console.warn('[github-client] settings DB read failed, using env fallback:', err);
  }
  return { token, repo };
}

async function gh<T>(path: string, init: RequestInit = {}): Promise<{ status: number; data: T | null; error?: string; headers: Headers }> {
  const { token } = await getConfig();
  const res = await fetch(path.startsWith("http") ? path : `${API}${path}`, {
    ...init,
    headers: {
      Accept: "application/vnd.github+json",
      Authorization: `Bearer ${token}`,
      "X-GitHub-Api-Version": "2022-11-28",
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
    cache: "no-store",
    signal: AbortSignal.timeout(25000),
  });
  const text = await res.text();
  const data = text ? (JSON.parse(text) as T) : null;
  if (!res.ok) {
    const msg = (data as { message?: string } | null)?.message ?? res.statusText;
    return { status: res.status, data, error: msg, headers: res.headers };
  }
  return { status: res.status, data, headers: res.headers };
}

export interface RawPR {
  number: number;
  title: string;
  state: string;
  merged: boolean;
  draft: boolean;
  html_url: string;
  updated_at: string;
  head: { ref: string; sha: string };
  base: { ref: string; sha: string };
  mergeable_state?: string;
  mergeable?: boolean | null;
}

export async function listOpenPRs(): Promise<RawPR[]> {
  const { repo } = await getConfig();
  const { data } = await gh<RawPR[]>(`/repos/${repo}/pulls?state=open&per_page=30&sort=updated&direction=desc`);
  // On API error `data` is the parsed error body (an object, not null) —
  // only pass through real arrays so callers never hit `.map is not a function`.
  return Array.isArray(data) ? data : [];
}

export async function compareHead(base: string, head: string): Promise<{ behindBy: number; aheadBy: number; status: string }> {
  const { repo } = await getConfig();
  const { data, error } = await gh<{ behind_by: number; ahead_by: number; status: string }>(
    `/repos/${repo}/compare/${base}...${head}`,
  );
  if (!data) return { behindBy: 0, aheadBy: 0, status: error ?? "unknown" };
  return { behindBy: data.behind_by, aheadBy: data.ahead_by, status: data.status };
}

export interface PRSummary {
  number: number;
  title: string;
  branch: string;
  base: string;
  state: string;
  merged: boolean;
  draft: boolean;
  mergeable: "mergeable" | "conflicting" | "unknown";
  behindBy: number;
  aheadBy: number;
  updatedAt: string;
  url: string;
  ciStatus: string | null;
}

/** Full PR intel: mergeability + behind/ahead + CI (combine PR API + compare). */
export async function getPRIntel(pr: RawPR): Promise<PRSummary> {
  const cmp = await compareHead(`${pr.base.ref}`, `${pr.head.ref}`);
  const dirty = pr.mergeable_state === "dirty" || pr.mergeable === false;
  let ciStatus: string | null = null;
  try {
    const { repo } = await getConfig();
    const { data } = await gh<{ workflow_runs: { head_sha: string; conclusion: string | null; status: string }[] }>(
      `/repos/${repo}/actions/runs?head_sha=${pr.head.sha}&per_page=3`,
    );
    const run = data?.workflow_runs?.[0];
    if (run) ciStatus = run.status === "completed" ? (run.conclusion ?? "unknown") : run.status;
  } catch (err) {
    console.warn('[github-client] CI status fetch failed (continuing without it):', err);
  }
  return {
    number: pr.number,
    title: pr.title,
    branch: pr.head.ref,
    base: pr.base.ref,
    state: pr.state,
    merged: pr.merged,
    draft: pr.draft,
    mergeable: dirty ? "conflicting" : pr.mergeable === true ? "mergeable" : "unknown",
    behindBy: cmp.behindBy,
    aheadBy: cmp.aheadBy,
    updatedAt: pr.updated_at,
    url: pr.html_url,
    ciStatus,
  };
}

export async function getDefaultBranchSha(): Promise<{ branch: string; sha: string }> {
  const { repo } = await getConfig();
  const { data } = await gh<{ default_branch: string; commit?: { sha: string } }>(`/repos/${repo}`);
  const branch = data?.default_branch ?? "main";
  const head = await gh<{ object: { sha: string } }>(`/repos/${repo}/git/ref/heads/${branch}`);
  return { branch, sha: head.data?.object?.sha ?? "" };
}

export async function listBranches(): Promise<{ name: string; sha: string; protected: boolean }[]> {
  const { repo } = await getConfig();
  const { data } = await gh<{ name: string; commit: { sha: string }; protected: boolean }[]>(`/repos/${repo}/branches?per_page=50`);
  return (Array.isArray(data) ? data : []).map((b) => ({ name: b.name, sha: b.commit.sha, protected: b.protected }));
}

/**
 * Merge default branch INTO a PR branch (updates the PR when main moved).
 * POST /repos/{o}/{r}/merges { base: prBranch, head: main } — creates merge commit.
 */
export async function mergeBaseIntoBranch(prBranch: string, baseBranch: string): Promise<{ ok: boolean; message: string }> {
  const { repo } = await getConfig();
  const { status, data, error } = await gh<{ sha: string }>(`/repos/${repo}/merges`, {
    method: "POST",
    body: JSON.stringify({ base: prBranch, head: baseBranch, commit_message: `chore(sync): merge ${baseBranch} into ${prBranch} — keep PR conflict-free (automated by Mission Control)` }),
  });
  if (status === 201) return { ok: true, message: `Merged ${baseBranch} into ${prBranch} (commit ${(data as { sha: string })?.sha?.slice(0, 7) ?? "?"})` };
  if (status === 204) return { ok: true, message: `${prBranch} already up to date with ${baseBranch}` };
  if (status === 409) return { ok: false, message: `Conflict merging ${baseBranch} into ${prBranch} — manual resolution required` };
  return { ok: false, message: error ?? `Merge failed (HTTP ${status})` };
}

export async function getWatchBranch(): Promise<string> {
  try {
    const s = await db.setting.findUnique({ where: { key: "watchBranch" } });
    return s?.value || "main";
  } catch {
    return "main";
  }
}

/**
 * THE standing directive, automated:
 * for each open PR: check conflict + behind count; if behind && clean → merge main into it; log everything.
 */
export async function runSyncSweep(autoSync: boolean): Promise<{
  prs: PRSummary[];
  mainHead: { branch: string; sha: string };
  actions: { prNumber: number; action: string; message: string }[];
}> {
  const mainHead = await getDefaultBranchSha();
  const raws = await listOpenPRs();
  const prs: PRSummary[] = [];
  const actions: { prNumber: number; action: string; message: string }[] = [];

  for (const raw of raws) {
    const intel = await getPRIntel(raw);
    prs.push(intel);

    let action = "checked";
    const mergeLabel =
      intel.mergeable === "mergeable" ? "conflict-free" : intel.mergeable === "conflicting" ? "CONFLICT" : "mergeability pending (CI running)";
    let message = `Checked — ${mergeLabel}, behind ${intel.behindBy}, ahead ${intel.aheadBy}`;

    if (!intel.merged && intel.behindBy > 0 && autoSync && intel.mergeable !== "conflicting") {
      const res = await mergeBaseIntoBranch(intel.branch, mainHead.branch);
      action = res.ok ? "synced_main" : "error";
      message = res.message;
      // refresh behind count after sync
      const fresh = await compareHead(intel.base, intel.branch);
      intel.behindBy = fresh.behindBy;
      intel.aheadBy = fresh.aheadBy;
      if (res.ok) intel.mergeable = "mergeable";
    } else if (intel.mergeable === "conflicting") {
      action = "skipped";
      message = `CONFLICT detected — ${intel.behindBy} behind; manual resolution needed`;
    }

    actions.push({ prNumber: intel.number, action, message });
    try {
      await db.gitSyncCheck.create({
        data: {
          prNumber: intel.number,
          branch: intel.branch,
          baseSha: mainHead.sha.slice(0, 12),
          headSha: raw.head.sha.slice(0, 12),
          conflict: intel.mergeable === "conflicting" ? "conflict" : intel.behindBy > 0 ? "behind" : "clean",
          behindBy: intel.behindBy,
          aheadBy: intel.aheadBy,
          action,
          detail: message,
        },
      });
      await db.activityEvent.create({
        data: {
          type: "git_sync",
          level: intel.mergeable === "conflicting" ? "warn" : action === "synced_main" ? "success" : "info",
          title: `PR #${intel.number} · ${action.replace("_", " ")}`,
          detail: message,
          meta: JSON.stringify({ branch: intel.branch, behindBy: intel.behindBy }),
        },
      });
    } catch (err) {
      console.warn('[github-client] git-sync audit log write failed (sweep continues):', err);
    }
  }
  return { prs, mainHead, actions };
}
