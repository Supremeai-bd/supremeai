import { NextResponse } from "next/server";
import { getDefaultBranchSha, getPRIntel, listBranches, listOpenPRs } from "@/lib/github-client";
import type { GitStatusData } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const mainHead = await getDefaultBranchSha();
    const raws = await listOpenPRs();
    const prs = await Promise.all(raws.map((r) => getPRIntel(r)));
    const branches = await listBranches();

    const data: GitStatusData = {
      branch: "feat/mission-control-console",
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
