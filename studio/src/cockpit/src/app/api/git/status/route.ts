import { NextResponse } from "next/server";
import { getDefaultBranchSha, getPRIntel, listBranches, listOpenPRs } from "@/lib/github-client";
import { getSettings } from "@/lib/settings";
import type { GitStatusData } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const mainHead = await getDefaultBranchSha();
    const raws = await listOpenPRs();
    const prs = await Promise.all(raws.map((r) => getPRIntel(r)));
    const branches = await listBranches();
    const settings = await getSettings();

    // Dynamic by Design: watch branch comes from settings; when an open PR
    // exists we surface its head branch as the tracked branch (no hardcode).
    const primary = prs.find((p) => p.state === "open") ?? prs[0];

    const data: GitStatusData = {
      branch: settings.watchBranch || "main",
      trackedBranch: primary?.branch ?? null,
      defaultBranch: mainHead.branch,
      mainHeadSha: mainHead.sha,
      prs,
      branches,
      checkedAt: new Date().toISOString(),
    };
    return NextResponse.json(data);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 500 });
  }
}
