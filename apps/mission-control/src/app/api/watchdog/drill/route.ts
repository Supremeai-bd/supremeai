import { NextResponse } from "next/server";
import { runWatchdogDrill } from "@/lib/watchdog";

export const dynamic = "force-dynamic";

/**
 * Watchdog drill — operator-triggered synthetic DOWN transition to verify the
 * alerting path end-to-end (journal + optional tower broadcast) without a real
 * outage. Clearly labeled as a drill everywhere it appears.
 */
export async function POST(request: Request) {
  try {
    const body = (await request.json().catch(() => ({}))) as { provider?: unknown };
    const provider = typeof body.provider === "string" ? body.provider.trim() : "";
    if (!provider) {
      return NextResponse.json({ ok: false, error: "provider is required" }, { status: 400 });
    }
    const result = await runWatchdogDrill(provider);
    if (!result.journaled && result.error) {
      return NextResponse.json({ ok: false, error: result.error }, { status: 400 });
    }
    return NextResponse.json({ ok: true, drill: result, checkedAt: new Date().toISOString() });
  } catch (err) {
    return NextResponse.json({ ok: false, error: String(err).slice(0, 200) }, { status: 500 });
  }
}
