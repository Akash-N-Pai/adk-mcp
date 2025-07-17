from pathlib import Path
import os
from dotenv import load_dotenv

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, TcpServerParameters

from local_mcp.prompt import DB_MCP_PROMPT

# Load environment variables from .env if present
load_dotenv()

# Read MCP server host/port from environment variables for flexibility
MCP_SERVER_HOST = os.getenv("MCP_SERVER_HOST", "localhost")  # Default to localhost for dev
MCP_SERVER_PORT = int(os.getenv("MCP_SERVER_PORT", 8001))    # Default port 8001

# Why: Using TcpServerParameters allows the agent to connect to a remote MCP server (e.g., on ATLAS Facility)
# instead of spawning a local process. This is necessary for production and more flexible for deployment.

root_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="htcondor_mcp_client_agent",  # ✅ More descriptive
    instruction=DB_MCP_PROMPT,
    tools=[
        MCPToolset(
            connection_params=TcpServerParameters(
                host=MCP_SERVER_HOST,
                port=MCP_SERVER_PORT,
            )
        )
    ],
)
