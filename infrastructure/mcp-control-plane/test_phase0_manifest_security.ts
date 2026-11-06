import assert from "node:assert/strict";
import { loadAuthoritativeServices, resolveServiceTarget } from "./src/diagnostics/service_manifest.js";
import { fingerprintSecret, redactSensitiveData } from "./src/diagnostics/redaction.js";

// 1. Service Manifest Discovery
const services = loadAuthoritativeServices();
assert.ok(Object.keys(services).length >= 5, "Service manifest should load multiple registered services");
assert.ok(services.api, "API gateway must be in service registry");
assert.ok(services.brain, "Brain node must be in service registry");
assert.equal(services.brain.repo, "Supremeai-bd/supremeai", "Brain node repo must point to Supremeai-bd/supremeai");

// 2. Alias resolution
const resolvedGateway = resolveServiceTarget("backend-api");
assert.ok(resolvedGateway, "backend-api alias must resolve to api");
assert.equal(resolvedGateway.name, "api");

const resolvedBrain = resolveServiceTarget("tiny-brain");
assert.ok(resolvedBrain, "tiny-brain alias must resolve to brain");
assert.equal(resolvedBrain.name, "brain");

// 3. Secret Redaction & Strict Drop
const masked = fingerprintSecret("my-super-secret-token-12345");
assert.ok(masked.startsWith("sha256:"), "Fingerprinted secret must start with sha256:");
assert.ok(!masked.includes("my-super-secret"), "Raw token must not appear in fingerprint");

const sanitized = redactSensitiveData({
  service: "backend-api",
  apiKey: "rnd_secret_key_1234567890",
  temp_clone_token: "ghs_12345abcdefg",
  headers: {
    authorization: "Bearer secret-jwt-payload-abc",
  },
  connectionString: "postgres://user:pass@db.supremeai.internal:5432/main",
  apiKeyRef: "infisical:RENDER_API_KEY_5",
  status: "healthy",
});

assert.equal((sanitized as any).status, "healthy");
assert.equal((sanitized as any).apiKey, undefined, "apiKey must be strictly dropped");
assert.equal((sanitized as any).temp_clone_token, undefined, "temp_clone_token must be strictly dropped");
assert.equal((sanitized as any).headers.authorization, undefined, "authorization must be strictly dropped");
assert.ok((sanitized as any).connectionString.startsWith("sha256:"), "connectionString should be fingerprinted");
assert.equal((sanitized as any).apiKeyRef, "infisical:RENDER_API_KEY_5", "Allowlisted non-secret metadata must be preserved");

console.log("Phase 0 service manifest and redaction tests passed successfully");
