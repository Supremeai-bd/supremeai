# SupremeAI Plugin SDK (V1)

Welcome to the SupremeAI Plugin Developer ecosystem. SupremeAI allows you to expose your tools, APIs, and business logic to our autonomous agents.

## V1: The Declarative Era
To ensure maximum security and stability for our users, **V1 of the Plugin Ecosystem is strictly declarative**.
You cannot upload raw Python or JavaScript files to be executed on our backend servers. 
Instead, SupremeAI leverages the **Model Context Protocol (MCP)**.

### How to build a V1 Plugin
1. Build an MCP Server (using any language: Python, TS, Go) and host it securely (must be HTTPS).
2. Ensure your MCP Server defines the tools you want the SupremeAI agent to use.
3. Submit a Plugin Manifest via the Community Portal.

### Example Manifest Submission
`json
{
  "name": "Acme Tools",
  "description": "Exposes Acme Corp's internal calculators to the agent.",
  "mcp_url": "https://mcp.acme.com/v1",
  "author": "dev@acme.com",
  "permission_schema": [
    {"name": "acme.read", "description": "Read acme data"}
  ]
}
`

### Security Guardrails
SupremeAI enforces strict SSRF protections.
- You cannot provide an mcp_url that points to localhost, 127.0.0.1, or any internal private IPs (e.g., 10.x.x.x).
- Your MCP server must be exposed to the public internet via https://.
- System capabilities (system.admin, db.write_raw) are strictly forbidden.
