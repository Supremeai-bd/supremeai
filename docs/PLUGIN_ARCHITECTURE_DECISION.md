# Architecture Decision Record: Plugin Ecosystem (V2.1)

## Context
SupremeAI currently uses a static, pre-defined IntegrationsManager for connecting external services (e.g., GitHub OAuth). It features a models/integration.py for credentials, a core/integrations/registry.py for system-level integrations (n8n, Appwrite), an mcp_client.py for MCP discovery, and a tools_registry for atomic agent capabilities.
To scale into an open ecosystem, a dynamic "Plugin / Apps Marketplace" is required. Initial plans suggested rewriting these layers.

## Decision
We will adopt the **V2.1 Existing-Codebase-Aligned Plugin Ecosystem**. This approach strictly reuses existing infrastructure and prevents duplicating architectural layers.

### 1. Database & Credential Binding
- **Decision:** Keep models/integration.py untouched as the core credential binding layer. 
- **Action:** Introduce a new models/user_plugin_installation.py that handles the plugin lifecycle (enabled, capabilities) and has a foreign key to integration_id. This prevents breaking the current GitHub OAuth persistence.

### 2. Registries
- **Decision:** Do not merge the System Integration Registry and the Plugin Marketplace Registry.
- **Action:** core/integrations/registry.py remains dedicated to backend infrastructure (n8n, Sentry). A new core/plugins/manifest_registry.py will be created exclusively for user-facing plugins (GitHub, Slack, MCP servers).

### 3. Tool Capabilities
- **Decision:** Do not create a separate plugin tool registry.
- **Action:** Reuse the existing 	ools_registry. A new CapabilityResolver will merge existing native tools, official plugin adapters, and MCP discovered tools into a single context for the agent.

### 4. MCP Modernization
- **Decision:** Do not build a completely new MCP stack from scratch.
- **Action:** Audit and upgrade the existing mcp_client.py to use the official MCP Python SDK v2 (Streamable HTTP, SSE support). Introduce an MCPSecurityGuard to enforce SSRF, DNS rebinding, and network egress policies for user-submitted MCP URLs.

### 5. Community Ecosystem Scope
- **Decision:** Restrict the v1 community portal to safe configurations.
- **Action:** Community plugins will only support declarative manifests + remote HTTPS APIs + MCP servers. Backend execution of community-submitted Python/JS code is out of scope for V1 due to security implications.

## Consequences
- **Positive:** Leverages existing codebase maturity. Zero regression on GitHub OAuth or current MCP behavior. Secure path to scale to thousands of plugins via MCP.
- **Negative:** Increased schema complexity (separating Installation vs Integration). Requires careful migration of the frontend IntegrationsManager.tsx to ensure legacy routes do not break.
