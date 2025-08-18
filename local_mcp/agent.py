from pathlib import Path
import logging
import os
from typing import Optional

from google.adk.agents import LlmAgent
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset, StdioServerParameters
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from typing import AsyncGenerator

from .prompt import DB_MCP_PROMPT
from .session_context_simple import get_simplified_session_context_manager

# IMPORTANT: Dynamically compute the absolute path to your server.py script
# The ADK agent for HTCondor/ATLAS Facility with session state management
PATH_TO_YOUR_MCP_SERVER_SCRIPT = str((Path(__file__).parent / "server.py").resolve())

# Initialize session context management
session_context_manager = get_simplified_session_context_manager()

logger = logging.getLogger(__name__)

class HTCondorAgent(LlmAgent):
    """Enhanced HTCondor agent with combined session and context management."""
    
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Enhanced agent implementation with combined session and context management."""
        logger.info(f"Starting HTCondor agent run for invocation {ctx.invocation_id}")
        
        # Get session context manager
        scm = get_simplified_session_context_manager()
        
        # Extract user and session info
        user_id = self._get_user_id_from_context(ctx)
        session_id = self._get_session_id_from_context(ctx)
        
        # Ensure session exists
        if not session_id:
            session_id = scm.create_session(user_id, {})
        
        # Get HTCondor context
        htcondor_context = scm.get_htcondor_context(session_id, user_id)
        
        logger.info(f"Processing request for user {user_id} in session {session_id}")
        
        # Add context information to memory
        scm.add_to_memory(
            user_id, 
            f"session_{session_id}_start", 
            {
                "invocation_id": ctx.invocation_id,
                "timestamp": ctx.user_content.timestamp if hasattr(ctx.user_content, 'timestamp') else None,
                "agent_name": self.name
            }
        )
        
        # Check if this is a returning user and provide context
        user_memory = scm.get_user_memory(user_id)
        if user_memory:
            # Add context about previous interactions
            recent_sessions = [k for k in user_memory.keys() if k.startswith("session_")]
            if recent_sessions:
                logger.info(f"User {user_id} has {len(recent_sessions)} previous sessions")
        
        # Delegate to parent implementation
        async for event in super()._run_async_impl(ctx):
            yield event
        
        # Log completion
        scm.add_to_memory(
            user_id,
            f"session_{session_id}_end",
            {
                "invocation_id": ctx.invocation_id,
                "completion_time": "completed"
            }
        )
        
        logger.info(f"Completed HTCondor agent run for invocation {ctx.invocation_id}")
    
    def _get_user_id_from_context(self, invocation_context: InvocationContext) -> str:
        """Extract user ID from invocation context."""
        # Try to get from session state first
        if invocation_context.session and invocation_context.session.state:
            user_id = invocation_context.session.state.get("user_id")
            if user_id:
                return user_id
        
        # Try to get from environment
        user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
        
        # Store in session state for future use
        if invocation_context.session:
            if not invocation_context.session.state:
                invocation_context.session.state = {}
            invocation_context.session.state["user_id"] = user_id
        
        return user_id
    
    def _get_session_id_from_context(self, invocation_context: InvocationContext) -> Optional[str]:
        """Extract session ID from invocation context."""
        if invocation_context.session:
            return invocation_context.session.id
        return None

# Create the enhanced agent
root_agent = HTCondorAgent(
    model="gemini-2.0-flash",
    name="htcondor_mcp_client_agent",
    instruction=DB_MCP_PROMPT,
    tools=[
        MCPToolset(
            connection_params=StdioServerParameters(
                command="python3",
                args=[PATH_TO_YOUR_MCP_SERVER_SCRIPT],
            ),
            # Add timeout configuration to prevent 5-second timeout errors
            #timeout=30.0  # 30 seconds timeout instead of default 5 seconds
        )
    ],
)

# Export session context manager for use in other modules
def get_session_context_manager():
    """Get the global session context manager instance."""
    return session_context_manager
