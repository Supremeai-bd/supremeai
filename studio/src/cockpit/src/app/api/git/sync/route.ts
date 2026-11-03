import { NextResponse } from "next/server";
import { runSyncSweep } from "@/lib/github-client";
import { getSettings } from "@/lib/settings";
import type { GitSyncResult } from "@/lib/mission-types";

export const dynamic = "force-dynamic";

/**
 * Standing directive executor: check every open PR against main;
 * merge main into stale-but-clean PR branches when autoSync is on.
 */
export async function POST() {
  try {
    const settings = await getSettings();
    const autoSync = settings.autoSyncPrs === "true";
    const sweep = await runSyncSweep(autoSync);

    const results: GitSyncResult[] = sweep.actions.map((a, i) => ({
      ok: a.action !== "error",
      action: a.action as GitSyncResult["action"],
      message: a.message,
      prNumber: a.prNumber,
      behindBy: sweep.prs[i]?.behindBy,
      conflict: sweep.prs[i]?.mergeable === "conflicting" ? "conflict" : "clean",
    }));

    return NextResponse.json({
      ok: true,
      autoSync,
      mainHead: sweep.mainHead,
      results,
      prs: sweep.prs,
      ranAt: new Date().toISOString(),
    });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err) }, { status: 500 });
  }
}
