import { Client } from "@modelcontextprotocol/sdk/client/index.js";
import { SSEClientTransport } from "@modelcontextprotocol/sdk/client/sse.js";

async function main() {
  const transport = new SSEClientTransport(new URL("http://localhost:3771/mcp"));
  const client = new Client({ name: "test-client", version: "1.0.0" });
  await client.connect(transport);
  
  console.log("Connected to MCP server");
  
  const result = await client.callTool({
    name: "resource.list",
    arguments: {}
  });
  
  console.log(JSON.stringify(result, null, 2));
  
  await client.close();
}

main().catch(console.error);
