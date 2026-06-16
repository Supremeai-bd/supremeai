import json
import subprocess
from typing import Dict, Any, List, Optional
from loguru import logger

class MCPClient:
    """
    Model Context Protocol (MCP) Client.
    Discovers tools and prompts from registered MCP servers.
    """
    
    def __init__(self, server_name: str, command: List[str]):
        self.server_name = server_name
        self.command = command
        self.process: Optional[subprocess.Popen] = None
        
    def connect(self) -> bool:
        """Starts the MCP server process with stdio transport."""
        try:
            logger.info(f"Connecting to MCP Server '{self.server_name}' using command: {self.command}")
            self.process = subprocess.Popen(
                self.command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )
            return True
        except Exception as e:
            logger.error(f"Failed to start MCP server {self.server_name}: {e}")
            return False
            
    def list_tools(self) -> List[Dict[str, Any]]:
        """Queries the MCP server for available tools."""
        if not self.process:
            return []
            
        request = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": 1
        }
        
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            
            # Read single line response
            line = self.process.stdout.readline()
            if line:
                response = json.loads(line)
                return response.get("result", {}).get("tools", [])
        except Exception as e:
            logger.error(f"Error querying MCP tools: {e}")
            
        return []

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Executes a tool on the MCP server."""
        if not self.process:
            return {"error": "Server not connected"}
            
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": name,
                "arguments": arguments
            },
            "id": 2
        }
        
        try:
            self.process.stdin.write(json.dumps(request) + "\n")
            self.process.stdin.flush()
            
            line = self.process.stdout.readline()
            if line:
                response = json.loads(line)
                return response.get("result", {})
        except Exception as e:
            logger.error(f"Error executing MCP tool '{name}': {e}")
            return {"error": str(e)}
            
        return {"error": "No response from server"}
        
    def disconnect(self):
        """Terminates the server connection."""
        if self.process:
            self.process.terminate()
            self.process.wait()
            self.process = None
            logger.info(f"Disconnected from MCP Server '{self.server_name}'")
