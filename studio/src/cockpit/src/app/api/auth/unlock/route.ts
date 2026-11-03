import { NextRequest, NextResponse } from "next/server";
import {
  getApiToken,
  signUnlockCookie,
  timingSafeEqualStr,
  UNLOCK_COOKIE,
  UNLOCK_TTL_SECONDS,
} from "@/lib/api-auth";

export const dynamic = "force-dynamic";

/**
 * FE-10 (issue #503): exchange the operator token for an HMAC-signed,
 * HttpOnly unlock cookie so the Mission Control browser UI can call /api/*
 * without ever holding the raw token in JS-accessible storage.
 *
 * POST { "token": "<MISSION_CONTROL_API_TOKEN>" } → 200 + Set-Cookie (12h)
 */
export async function POST(request: NextRequest) {
  const expected = getApiToken();
  if (!expected) {
    return NextResponse.json(
      { error: "MISSION_CONTROL_API_TOKEN is not configured on the server." },
      { status: 503 },
    );
  }

  let token = "";
  try {
    const body = (await request.json()) as { token?: unknown };
    if (typeof body.token === "string") token = body.token.trim();
  } catch {
    return NextResponse.json({ error: "Invalid JSON body" }, { status: 400 });
  }

  if (!token || !timingSafeEqualStr(token, expected)) {
    return NextResponse.json({ error: "Invalid operator token" }, { status: 401 });
  }

  const value = await signUnlockCookie(expected, Math.floor(Date.now() / 1000));
  const res = NextResponse.json({ ok: true, ttlSeconds: UNLOCK_TTL_SECONDS });
  res.cookies.set(UNLOCK_COOKIE, value, {
    httpOnly: true,
    sameSite: "strict",
    secure: process.env.NODE_ENV === "production",
    path: "/",
    maxAge: UNLOCK_TTL_SECONDS,
  });
  return res;
}
