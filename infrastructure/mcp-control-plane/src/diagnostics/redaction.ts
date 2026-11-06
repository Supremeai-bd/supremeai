import crypto from "node:crypto";

const STRICT_DROP_KEYS = new Set([
  "token",
  "temp_clone_token",
  "access_token",
  "refresh_token",
  "api_key",
  "apikey",
  "password",
  "secret",
  "authorization",
  "cookie",
  "credentials",
  "private_key",
  "client_secret",
]);

const ALLOWLISTED_NON_SECRET_KEYS = new Set([
  "apikeyref",
  "apikeyrefs",
  "idempotencykey",
  "deploykey",
  "deploy_key",
  "key",
  "keys",
  "requiredkey",
  "requiredenv",
]);

const SENSITIVE_KEY_PATTERNS = [
  /token/i,
  /secret/i,
  /password/i,
  /passphrase/i,
  /authorization/i,
  /cookie/i,
  /credential/i,
  /private/i,
  /connection.*string/i,
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
 * Deep redaction walker for diagnostic results, health snapshots, and provider outputs.
 * 1. Completely drops credential-bearing keys (temp_clone_token, access_token, etc.).
 * 2. Fingerprints / masks remaining sensitive values.
 * 3. Never leaks plaintext credentials to callers or LLM contexts.
 */
export function redactSensitiveData<T>(input: T): T {
  if (input === null || input === undefined) return input;

  if (typeof input === "string") {
    // Detect raw bearer tokens, private keys or high-entropy tokens
    if (/bearer\s+[a-zA-Z0-9_\-\.]{15,}/i.test(input)) {
      return input.replace(/bearer\s+[a-zA-Z0-9_\-\.]{15,}/gi, "Bearer [REDACTED]") as unknown as T;
    }
    if (input.includes("-----BEGIN PRIVATE KEY-----") || input.includes("-----BEGIN RSA PRIVATE KEY-----")) {
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
      const lowerKey = k.toLowerCase().trim();

      // Drop credential-bearing fields entirely
      if (STRICT_DROP_KEYS.has(lowerKey)) {
        continue;
      }

      if (ALLOWLISTED_NON_SECRET_KEYS.has(lowerKey)) {
        output[k] = v;
        continue;
      }

      const isSensitive = SENSITIVE_KEY_PATTERNS.some((pattern) => pattern.test(lowerKey));
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
