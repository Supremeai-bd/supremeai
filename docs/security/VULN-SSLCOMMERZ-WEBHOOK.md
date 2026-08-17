# Security Advisory: SSLCommerz Webhook Vulnerability (VULN-SSLCOMMERZ-WEBHOOK)

**Severity**: CRITICAL
**Status**: RESOLVED
**Date Discovered**: 2026-07-15
**Affected Modules**:
- `backend/api/routes/billing_api.py` (`POST /api/billing/webhook/sslcommerz`)
- `apps/mobile/lib/services/payment_gateway_bridge.dart`
- `apps/mobile/lib/screens/wallet_screen.dart`

## Description of Vulnerability
An architectural flaw allowed arbitrary actors to credit arbitrary amounts of funds to any user's wallet without processing a legitimate payment.

The `POST /api/billing/webhook/sslcommerz` endpoint was previously trusting the client-provided JSON payload (specifically the `status` and `amount` fields) without any server-side validation or signature verification. An attacker could simply issue an unauthenticated HTTP POST request to this endpoint simulating a successful payment, and the backend would blindly trust the payload and credit the user's wallet.

Furthermore, the mobile application contained active "simulation" code that bypassed the real payment SDK, directly invoking this webhook endpoint with fake data to credit the account during development. This code was left in the production path.

## Remediation Steps Taken
1. **Server-Side Validation**: The `billing_api.py` endpoint was rewritten to integrate with SSLCommerz's official Validation API. It now extracts only the `val_id` from the incoming request and performs a server-to-server call to `securepay.sslcommerz.com` to verify the transaction status and authoritative amount.
2. **Client-Side Sanitization**: The fake local webhook caller (`_simulateWebhookConfirmation`) was entirely removed from `wallet_screen.dart`. The `payment_gateway_bridge.dart` was updated to remove the insecure `_showSimulatedWebview` modal. It now explicitly throws an `UnimplementedError` to force proper integration of real payment SDKs before deployment.

## Future Prevention
- **Never trust client payloads** for critical state transitions, especially financial transactions. Always rely on verifiable server-to-server communication or signed webhooks.
- Ensure development/mocking code is strictly gated (e.g., behind `kDebugMode` in Flutter) or stripped entirely from production builds.
- The CI `find_stub_data.py` script has been updated to detect mock logic, providing a defense-in-depth measure against merging similar placeholders in the future.
