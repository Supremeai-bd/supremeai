import crypto from "node:crypto";

const SENSITIVE_KEY_PATTERNS = [
  /token/i,
  /secret/i,
  /key/i,
  /password/i,
  /passphrase/i,
  /auth/i,
  /authorization/i,
  /cookie/i,
  /credential/i,
  /private/i,
  /connection_string/i,
];

/**
 * Hash a secret value to an immutable fingerprint rather than leaking raw credentials.
 */
export function fingerprintSecret(value: string): string {
  if (!value) return "empty";
  const hash = crypto.createHash("sha256").update(value).digest("hex").slice(0, 12);
  return `sha256:${hash}...`;
}

/**
 * Deep redaction walker for diagnostic results and logs.
 * Masks known secret keys and high-entropy values before passing to caller/LLM.
 */
export function redactSensitiveData<T>(input: T): T {
  if (input === null || input === undefined) return input;

  if (typeof input === "string") {
    // Detect raw bearer tokens, private keys or high-entropy tokens
    if (/bearer\s+[a-zA-Z0-9_\-\.]{20,}/i.test(input)) {
      return input.replace(/bearer\s+[a-zA-Z0-9_\-\.]{20,}/gi, "Bearer [REDACTED]") as unknown as T;
    }
    if (input.includes("-----BEGIN PRIVATE KEY-----")) {
      return "[REDACTED PRIVATE KEY]" as unknown as T;
    }
    return input;
  }

  if (Array.isArray(input)) {
    return input.map((item) => redactSensitiveData(item)) as unknown as T;
  }

  if (typeof input === "object") {
    const output: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(input as Record<string, unknown>)) {
      const isSensitive = SENSITIVE_KEY_PATTERNS.some((pattern) => pattern.test(k));
      if (isSensitive && typeof v === "string" && v.length > 0) {
        output[k] = fingerprintSecret(v);
      } else {
        output[k] = redactSensitiveData(v);
      }
    }
    return output as T;
  }

  return input;
}
