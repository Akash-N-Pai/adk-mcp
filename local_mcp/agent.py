from pathlib import Path

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters

from .prompt import DB_MCP_PROMPT
from .session import SessionManager

# IMPORTANT: Dynamically compute the absolute path to your server.py script
# The ADK agent for HTCondor/ATLAS Facility with session state management
PATH_TO_YOUR_MCP_SERVER_SCRIPT = str((Path(__file__).parent / "server.py").resolve())

# Initialize session management
session_manager = SessionManager()

root_agent = LlmAgent(
    model="gemini-2.0-flash",
    name="htcondor_mcp_client_agent",  # ✅ More descriptive
    instruction=DB_MCP_PROMPT,
    tools=[
        MCPToolset(
            connection_params=StdioServerParameters(
                command="python3",
                args=[PATH_TO_YOUR_MCP_SERVER_SCRIPT],
            )
            # tool_filter=['list_tables'] # Optional: ensure only specific tools are loaded
        )
    ],
)

# Export session manager for use in other modules
def get_session_manager():
    """Get the global session manager instance."""
    return session_manager
