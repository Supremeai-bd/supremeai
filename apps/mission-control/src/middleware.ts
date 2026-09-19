import { NextRequest, NextResponse } from "next/server";
import {
  getApiToken,
  timingSafeEqualStr,
  verifyUnlockCookie,
  UNLOCK_COOKIE,
} from "@/lib/api-auth";

/**
 * FE-10 (issue #503): authentication gate for every Mission Control API route.
 *
 * Previously `/api/tower/call` (and every other /api route) accepted
 * unauthenticated POSTs and invoked arbitrary MCP tower tools with the
 * configured admin key — an RCE-equivalent surface reachable by anyone who
 * could hit the deployment.
 *
 * Policy:
 *  - Requests presenting the operator token via `Authorization: Bearer <t>`
 *    or `X-Admin-Key: <t>` pass.
 *  - Browsers pass via the HttpOnly unlock cookie issued by
 *    POST /api/auth/unlock (HMAC-signed with the operator token).
 *  - `/api` (root) and `/api/auth/unlock` stay public.
 *  - If MISSION_CONTROL_API_TOKEN is not configured:
 *      • development → allowed (local friction-free dev), warning logged
 *      • production  → FAIL CLOSED (503) so an unconfigured deploy is never
 *        an open proxy to the tower.
 */
export async function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl;

  // Always public endpoints
  if (pathname === "/api" || pathname === "/api/auth/unlock") {
    return NextResponse.next();
  }

  const token = getApiToken();

  if (!token) {
    if (process.env.NODE_ENV === "production") {
      return NextResponse.json(
        {
          error:
            "Mission Control API is locked: MISSION_CONTROL_API_TOKEN is not configured. " +
            "Set it in the environment, unlock with POST /api/auth/unlock, then retry.",
        },
        { status: 503 },
      );
    }
    // Dev with no token configured: allow, but surface a hint via header.
    const res = NextResponse.next();
    res.headers.set("x-mission-auth", "dev-bypass");
    return res;
  }

  // 1) Header auth: Authorization: Bearer <token> | X-Admin-Key: <token>
  const authHeader = request.headers.get("authorization") || "";
  const bearer = authHeader.toLowerCase().startsWith("bearer ")
    ? authHeader.slice(7).trim()
    : "";
  const adminKey = request.headers.get("x-admin-key") || "";
  if (timingSafeEqualStr(bearer, token) || timingSafeEqualStr(adminKey, token)) {
    return NextResponse.next();
  }

  // 2) Cookie auth: HMAC-signed unlock cookie
  const cookieValue = request.cookies.get(UNLOCK_COOKIE)?.value;
  if (await verifyUnlockCookie(cookieValue, token)) {
    return NextResponse.next();
  }

  return NextResponse.json(
    { error: "Unauthorized — unlock via POST /api/auth/unlock or send Authorization: Bearer <token>" },
    { status: 401, headers: { "x-mission-auth": "required" } },
  );
}

export const config = {
  matcher: ["/api/:path*"],
};
