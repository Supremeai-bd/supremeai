import crypto from "node:crypto";
import { toServiceRef } from "../../diagnostics/service_manifest.js";

export type SupportedCodecVersion = "v1";

export interface RedisKeyDescriptor {
  environment?: "development" | "staging" | "production";
  service: string;
  namespace: string;
  entity: string;
  id: string;
}

export interface RedisEncodedEnvelope<T = unknown> {
  codecVersion: SupportedCodecVersion;
  schemaName: string;
  schemaHash: string;
  canonicalServiceId: string;
  encodedAt: string;
  payload: T;
}

export type RedisDecodeOutcome<T = unknown> =
  | {
      status: "ok";
      envelope: RedisEncodedEnvelope<T>;
      payload: T;
    }
  | {
      status: "quarantined";
      reason:
        | "EMPTY_PAYLOAD"
        | "CORRUPT_JSON"
        | "UNSUPPORTED_CODEC_VERSION"
        | "SCHEMA_HASH_MISMATCH"
        | "MALFORMED_ENVELOPE";
      rawSample: string;
    };

/**
 * Computes a deterministic 12-char SHA-256 fingerprint for a schema identifier.
 */
export function computeSchemaHash(schemaName: string, version: SupportedCodecVersion = "v1"): string {
  return crypto
    .createHash("sha256")
    .update(`supremeai:${version}:${schemaName.trim().toLowerCase()}`)
    .digest("hex")
    .slice(0, 12);
}

/**
 * Enforces canonical Redis key formatting across the control plane:
 * supremeai:<env>:<canonicalServiceId>:<namespace>:<entity>:<id>
 */
export function buildCanonicalRedisKey(desc: RedisKeyDescriptor): string {
  const ref = toServiceRef(desc.service);
  const canonicalId = ref?.canonicalServiceId ?? desc.service.trim().toLowerCase();
  const env = desc.environment ?? ref?.environment ?? "production";
  const clean = (val: string) => val.trim().replace(/[^a-zA-Z0-9._-]/g, "_");

  return [
    "supremeai",
    clean(env),
    clean(canonicalId),
    clean(desc.namespace),
    clean(desc.entity),
    clean(desc.id),
  ].join(":");
}

/**
 * Wraps a value into a versioned Redis codec envelope with schema hash provenance.
 */
export function encodeRedisPayload<T>(
  payload: T,
  schemaName: string,
  service = "mcp",
): string {
  const ref = toServiceRef(service);
  const canonicalServiceId = ref?.canonicalServiceId ?? service;
  const envelope: RedisEncodedEnvelope<T> = {
    codecVersion: "v1",
    schemaName,
    schemaHash: computeSchemaHash(schemaName, "v1"),
    canonicalServiceId,
    encodedAt: new Date().toISOString(),
    payload,
  };
  return JSON.stringify(envelope);
}

/**
 * Safely decodes a Redis payload. Corrupt JSON, unknown codec versions, or
 * mismatched schema hashes are quarantined instead of crashing the caller.
 */
export function decodeRedisPayload<T = unknown>(
  raw: string | null | undefined,
  expectedSchemaName?: string,
): RedisDecodeOutcome<T> {
  if (!raw || typeof raw !== "string" || !raw.trim()) {
    return {
      status: "quarantined",
      reason: "EMPTY_PAYLOAD",
      rawSample: "",
    };
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return {
      status: "quarantined",
      reason: "CORRUPT_JSON",
      rawSample: raw.slice(0, 120),
    };
  }

  if (!parsed || typeof parsed !== "object") {
    return {
      status: "quarantined",
      reason: "MALFORMED_ENVELOPE",
      rawSample: raw.slice(0, 120),
    };
  }

  const obj = parsed as Record<string, unknown>;
  if (obj.codecVersion !== "v1") {
    return {
      status: "quarantined",
      reason: "UNSUPPORTED_CODEC_VERSION",
      rawSample: raw.slice(0, 120),
    };
  }

  if (
    typeof obj.schemaName !== "string" ||
    typeof obj.schemaHash !== "string" ||
    !("payload" in obj)
  ) {
    return {
      status: "quarantined",
      reason: "MALFORMED_ENVELOPE",
      rawSample: raw.slice(0, 120),
    };
  }

  if (expectedSchemaName) {
    const expectedHash = computeSchemaHash(expectedSchemaName, "v1");
    if (obj.schemaHash !== expectedHash) {
      return {
        status: "quarantined",
        reason: "SCHEMA_HASH_MISMATCH",
        rawSample: raw.slice(0, 120),
      };
    }
  }

  const envelope = obj as unknown as RedisEncodedEnvelope<T>;
  return {
    status: "ok",
    envelope,
    payload: envelope.payload,
  };
}

