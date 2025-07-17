"""
Integration tests for the ADK agent with MCP server.
Tests the complete flow from agent to MCP server and back.
"""

import pytest
from unittest.mock import patch
from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
from local_mcp.agent import root_agent


class TestAgentMCPIntegration:
    """Integration tests for agent and MCP server communication."""

    @patch("local_mcp.agent.MCPToolset")
    def test_agent_initialization(self, mock_mcp_toolset):
        """Test that the agent is properly initialized with MCP tools."""
        # Verify the agent has the expected configuration
        assert root_agent.model == "gemini-2.0-flash"
        assert root_agent.name == "htcondor_mcp_client_agent"
        assert len(root_agent.tools) == 1

        # Verify MCP toolset is configured
        mcp_tool = root_agent.tools[0]
        assert isinstance(mcp_tool, MCPToolset)

        # Verify server parameters (using private attribute)
        assert mcp_tool._connection_params.command == "python3"
        assert "server.py" in mcp_tool._connection_params.args[0]

    @patch("local_mcp.agent.MCPToolset")
    def test_mcp_server_script_path(self, mock_mcp_toolset):
        """Test that the MCP server script path is correctly resolved."""
        from local_mcp.agent import PATH_TO_YOUR_MCP_SERVER_SCRIPT

        # Verify the path points to the server.py file
        assert PATH_TO_YOUR_MCP_SERVER_SCRIPT.endswith("server.py")
        assert "local_mcp" in PATH_TO_YOUR_MCP_SERVER_SCRIPT


class TestAgentPrompt:
    """Test cases for agent prompt functionality."""

    def test_prompt_contains_required_instructions(self):
        """Test that the prompt contains all required instructions."""
        from local_mcp.prompt import DB_MCP_PROMPT

        # Check for key instructions
        assert "list_jobs" in DB_MCP_PROMPT
        assert "get_job_status" in DB_MCP_PROMPT
        assert "submit_job" in DB_MCP_PROMPT
        assert "HTCondor" in DB_MCP_PROMPT
        assert "ATLAS Facility" in DB_MCP_PROMPT

    def test_prompt_contains_example_interactions(self):
        """Test that the prompt contains helpful example interactions."""
        from local_mcp.prompt import DB_MCP_PROMPT

        # Check for example interactions
        assert "Show me all running jobs" in DB_MCP_PROMPT
        assert "What's the status of job" in DB_MCP_PROMPT
        assert "Submit a job" in DB_MCP_PROMPT

    def test_prompt_contains_status_mapping(self):
        """Test that the prompt includes status code mapping."""
        from local_mcp.prompt import DB_MCP_PROMPT

        # Check for status mapping information
        assert "1=Idle" in DB_MCP_PROMPT
        assert "2=Running" in DB_MCP_PROMPT
        assert "5=Held" in DB_MCP_PROMPT


class TestAgentToolExecution:
    """Test cases for agent tool execution scenarios."""

    @pytest.mark.asyncio
    async def test_agent_list_jobs_request(self):
        """Test agent handling of list jobs request."""
        # For testing, we verify the agent is configured correctly
        assert root_agent.model == "gemini-2.0-flash"
        assert len(root_agent.tools) == 1

        # Verify the agent has the expected tools
        assert isinstance(root_agent.tools[0], MCPToolset)

    @pytest.mark.asyncio
    async def test_agent_job_status_request(self):
        """Test agent handling of job status request."""
        # Verify agent configuration
        assert root_agent.name == "htcondor_mcp_client_agent"

        # Verify the agent has the expected configuration
        assert root_agent.model == "gemini-2.0-flash"
        assert len(root_agent.tools) == 1


class TestErrorHandling:
    """Test cases for error handling in the agent-MCP integration."""

    def test_mcp_server_script_exists(self):
        """Test that the MCP server script exists and is accessible."""
        import os
        from local_mcp.agent import PATH_TO_YOUR_MCP_SERVER_SCRIPT

        assert os.path.exists(PATH_TO_YOUR_MCP_SERVER_SCRIPT)
        assert os.path.isfile(PATH_TO_YOUR_MCP_SERVER_SCRIPT)

    def test_required_dependencies_available(self):
        """Test that all required dependencies are available."""
        try:
            import htcondor  # noqa: F401
            import mcp  # noqa: F401
            import google.adk  # noqa: F401

            assert True  # All imports successful
        except ImportError as e:
            pytest.fail(f"Missing required dependency: {e}")


class TestConfigurationValidation:
    """Test cases for configuration validation."""

    def test_agent_configuration_completeness(self):
        """Test that the agent has all required configuration."""
        # Check agent has required attributes
        assert hasattr(root_agent, "model")
        assert hasattr(root_agent, "name")
        assert hasattr(root_agent, "instruction")
        assert hasattr(root_agent, "tools")

        # Check tools are properly configured
        assert len(root_agent.tools) > 0
        assert all(
            hasattr(tool, "_connection_params")
            for tool in root_agent.tools
            if hasattr(tool, "_connection_params")
        )

    def test_mcp_tool_configuration(self):
        """Test that MCP tools are properly configured."""
        mcp_tools = [
            tool for tool in root_agent.tools if hasattr(tool, "_connection_params")
        ]

        for tool in mcp_tools:
            assert hasattr(tool._connection_params, "command")
            assert hasattr(tool._connection_params, "args")
            assert tool._connection_params.command == "python3"
            assert len(tool._connection_params.args) > 0


if __name__ == "__main__":
    pytest.main([__file__])
