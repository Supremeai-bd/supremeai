/**
 * RFC 6238 Time-based One-Time Password (TOTP) utility
 * Pure Node.js crypto implementation (zero external dependency).
 * Compatible with Google Authenticator, Microsoft Authenticator, 1Password, and Apple Passwords.
 */
import { createHmac, timingSafeEqual } from "node:crypto";

const BASE32_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567";

/**
 * Decodes a Base32 string (case-insensitive, ignores spaces/hyphens/padding) into Buffer.
 */
export function base32ToBuffer(base32: string): Buffer {
  const clean = base32.toUpperCase().replace(/[\s\-=]/g, "");
  let bits = 0;
  let value = 0;
  const bytes: number[] = [];

  for (let i = 0; i < clean.length; i++) {
    const idx = BASE32_ALPHABET.indexOf(clean[i]);
    if (idx === -1) continue;
    value = (value << 5) | idx;
    bits += 5;
    if (bits >= 8) {
      bytes.push((value >>> (bits - 8)) & 255);
      bits -= 8;
    }
  }
  return Buffer.from(bytes);
}

/**
 * Computes a 6-digit TOTP code for a specific counter step (RFC 6238 / RFC 4226).
 */
export function generateTotpCode(secretBase32: string, counter: number): string {
  const key = base32ToBuffer(secretBase32);
  const buf = Buffer.alloc(8);
  buf.writeBigUInt64BE(BigInt(counter), 0);

  const hmac = createHmac("sha1", key).update(buf).digest();
  const offset = hmac[hmac.length - 1] & 0x0f;
  const codeInt =
    ((hmac[offset] & 0x7f) << 24) |
    ((hmac[offset + 1] & 0xff) << 16) |
    ((hmac[offset + 2] & 0xff) << 8) |
    (hmac[offset + 3] & 0xff);

  return (codeInt % 1000000).toString().padStart(6, "0");
}

/**
 * Verifies a 6-digit TOTP code against a Base32 secret.
 * Allows +/- windowSteps (default 1 = +/- 30 seconds drift margin).
 */
export function verifyTotp(
  code: string,
  secretBase32: string,
  windowSteps = 1,
  timeMs = Date.now()
): boolean {
  const cleanCode = code.trim().replace(/\s+/g, "");
  if (!/^\d{6}$/.test(cleanCode)) return false;

  const currentCounter = Math.floor(timeMs / 1000 / 30);
  for (let i = -windowSteps; i <= windowSteps; i++) {
    const expected = generateTotpCode(secretBase32, currentCounter + i);
    if (expected.length === cleanCode.length && timingSafeEqual(Buffer.from(expected), Buffer.from(cleanCode))) {
      return true;
    }
  }
  return false;
}
