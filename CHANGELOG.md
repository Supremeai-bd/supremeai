# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Security
- Removed hardcoded 2FA backdoor in admin TOTP verification
- Replaced fail-open mock-token auth stubs with fail-closed imports
- Fixed broken token issuance in gateway (keygen import failure)
- Added JWT issuer/audience verification
- Added SSE upstream cleanup on client disconnect

### Fixed
- Gateway `generate_key` import path corrected (`gateway.service.keygen`)
- Token issuance now fails with 503 instead of returning unverifiable tokens
- Core app factory boots from the repository root with deterministic core import precedence
- Duplicate router/model imports no longer break router mount hygiene
- Thread-offloaded route callbacks bind their loop variables
- One HMAC-authenticated comment webhook dispatches GitHub events without route shadowing
- Living Engine no longer imports retired adapters; provider errors and empty completions fail closed
- Living Engine invokes the existing self-reflection loop on success and failure and serializes its feedback

### Added
- Deployment rollback workflow and runbook
- Router mount hygiene guard tests
- Auth stub detection guard test
- Per-app router registration counts and degraded health for recorded mount failures
- Cross-issuer JWT, root-factory, and heavy-CI scope regression coverage
- Isolated MCP mailbox delivery, acknowledgment, subscription, and tenant-boundary coverage
- Gateway added to CI lint scope

### Changed
- CI ruff scope expanded to include `gateway/`
- Removed dead Studio Frontend Smoke Check from CI pipeline
- Local, Ubuntu fallback, and emergency heavy CI jobs discover all four Python test domains and enforce 80% core/gateway coverage
- Heavy CI installs the MCP 1.x SDK required by the core server contract
- Local multi-command verification steps stop on each native command failure
- Brain and swarm worker images use a verified Python 3.12 digest; obsolete FROM baseline entries are removed
- Retired synthetic adapter tests now cover gateway routing, malformed responses, cancellation, and the generated-code default-deny gate
