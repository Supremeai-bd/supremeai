"use client";

/**
 * FE-10 (issue #503): client-side companion to the API auth middleware.
 *
 * Components across the app call `fetch("/api/...")` directly. Instead of
 * editing every call site, this single component:
 *   1. Intercepts 401 responses from /api/* via a global fetch patch.
 *   2. Shows a minimal unlock dialog asking for the operator token.
 *   3. POSTs it to /api/auth/unlock → server sets an HttpOnly signed cookie.
 *   4. Reloads so the original request flow resumes authenticated.
 *
 * The raw token is never persisted client-side (only inside the form field
 * until the page reloads).
 */

import { useCallback, useEffect, useRef, useState } from "react";

export function ApiGate() {
  const [open, setOpen] = useState(false);
  const [token, setToken] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const patched = useRef(false);

  useEffect(() => {
    if (patched.current) return;
    patched.current = true;

    const originalFetch = window.fetch.bind(window);
    window.fetch = async (...args: Parameters<typeof fetch>) => {
      const res = await originalFetch(...args);
      try {
        const url =
          typeof args[0] === "string"
            ? args[0]
            : args[0] instanceof URL
              ? args[0].pathname
              : (args[0] as Request).url ?? "";
        const path = url.startsWith("http")
          ? new URL(url).pathname
          : url;
        if (path.startsWith("/api/") && res.status === 401) {
          setOpen(true);
        }
      } catch {
        /* never break the calling code */
      }
      return res;
    };
    return () => {
      window.fetch = originalFetch;
      patched.current = false;
    };
  }, []);

  const unlock = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/auth/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token }),
      });
      if (res.ok) {
        window.location.reload();
        return;
      }
      const data = (await res.json().catch(() => ({}))) as { error?: string };
      setError(data.error || `Unlock failed (${res.status})`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unlock request failed");
    } finally {
      setBusy(false);
    }
  }, [token]);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Mission Control unlock"
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 9999,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "rgba(0,0,0,0.6)",
        backdropFilter: "blur(4px)",
      }}
    >
      <div
        style={{
          background: "#10151a",
          color: "#e6edf3",
          border: "1px solid #2d3640",
          borderRadius: 12,
          padding: 24,
          width: "min(420px, calc(100vw - 32px))",
          boxShadow: "0 16px 48px rgba(0,0,0,0.5)",
        }}
      >
        <h2 style={{ margin: "0 0 8px", fontSize: 18, fontWeight: 600 }}>
          🔒 Mission Control is locked
        </h2>
        <p style={{ margin: "0 0 16px", fontSize: 13, color: "#9aa7b4" }}>
          API access requires the operator token. It is exchanged for an
          HttpOnly cookie — the token itself is never stored in the browser.
        </p>
        <input
          type="password"
          value={token}
          onChange={(e) => setToken(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter" && token) void unlock();
          }}
          placeholder="Operator token (MISSION_CONTROL_API_TOKEN)"
          autoFocus
          style={{
            width: "100%",
            boxSizing: "border-box",
            padding: "10px 12px",
            borderRadius: 8,
            border: "1px solid #2d3640",
            background: "#0b0f14",
            color: "#e6edf3",
            fontSize: 13,
            marginBottom: 12,
          }}
        />
        {error && (
          <p style={{ margin: "0 0 12px", fontSize: 12, color: "#f87171" }}>{error}</p>
        )}
        <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
          <button
            onClick={() => setOpen(false)}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              border: "1px solid #2d3640",
              background: "transparent",
              color: "#9aa7b4",
              fontSize: 13,
              cursor: "pointer",
            }}
          >
            Cancel
          </button>
          <button
            onClick={() => void unlock()}
            disabled={busy || !token}
            style={{
              padding: "8px 14px",
              borderRadius: 8,
              border: "none",
              background: busy || !token ? "#24423a" : "#16a34a",
              color: "#fff",
              fontSize: 13,
              fontWeight: 600,
              cursor: busy || !token ? "not-allowed" : "pointer",
            }}
          >
            {busy ? "Unlocking…" : "Unlock"}
          </button>
        </div>
      </div>
    </div>
  );
}

export default ApiGate;
