#!/usr/bin/env python3
"""
Pytest test file for evaluating the HTCondor agent using ADK evaluation framework.
"""

import pytest
import asyncio
import os
import sys
from pathlib import Path

# Add the current directory to Python path to import local_mcp
sys.path.insert(0, str(Path(__file__).parent))

# Import the ADK evaluation framework
from google.adk.evaluation.agent_evaluator import AgentEvaluator

# Import your agent
from local_mcp import root_agent

class TestHTCondorAgentEvaluation:
    """Test class for HTCondor agent evaluation."""
    
    @pytest.mark.asyncio
    async def test_htcondor_agent_comprehensive_evaluation(self):
        """Test the HTCondor agent with comprehensive evaluation cases."""
        print("🚀 Starting HTCondor agent comprehensive evaluation...")
        
        # Get the path to the evaluation file
        eval_file_path = Path(__file__).parent / "htcondor_agent_evaluation.test.json"
        
        # Verify the evaluation file exists
        if not eval_file_path.exists():
            pytest.fail(f"Evaluation file not found: {eval_file_path}")
        
        print(f"📋 Using evaluation file: {eval_file_path}")
        
        try:
            # Run the evaluation using ADK AgentEvaluator
            await AgentEvaluator.evaluate(
                agent_module="local_mcp",  # Your agent module
                eval_dataset_file_path_or_dir=str(eval_file_path),
            )
            print("✅ HTCondor agent evaluation completed successfully!")
            
        except Exception as e:
            print(f"❌ Evaluation failed: {e}")
            pytest.fail(f"Agent evaluation failed: {e}")
    
    @pytest.mark.asyncio
    async def test_htcondor_agent_basic_functionality(self):
        """Test basic HTCondor agent functionality."""
        print("🧪 Testing basic HTCondor agent functionality...")
        
        # Test that the agent can be instantiated
        assert root_agent is not None, "Root agent should be defined"
        assert hasattr(root_agent, 'name'), "Agent should have a name"
        assert root_agent.name == "htcondor_mcp_client_agent", f"Expected agent name 'htcondor_mcp_client_agent', got '{root_agent.name}'"
        
        print(f"✅ Agent '{root_agent.name}' is properly configured")
    
    @pytest.mark.asyncio
    async def test_htcondor_agent_tools_available(self):
        """Test that HTCondor agent has the expected tools."""
        print("🔧 Testing HTCondor agent tools...")
        
        # Check that the agent has tools
        assert hasattr(root_agent, 'tools'), "Agent should have tools"
        assert len(root_agent.tools) > 0, "Agent should have at least one tool"
        
        # Get tool names
        tool_names = [tool.name for tool in root_agent.tools]
        print(f"📦 Available tools: {tool_names}")
        
        # Check for essential HTCondor tools
        essential_tools = [
            "list_jobs",
            "get_job_status", 
            "submit_job",
            "list_htcondor_tools"
        ]
        
        for tool_name in essential_tools:
            assert tool_name in tool_names, f"Essential tool '{tool_name}' should be available"
        
        print("✅ All essential HTCondor tools are available")
    
    @pytest.mark.asyncio
    async def test_htcondor_agent_model_configuration(self):
        """Test that HTCondor agent has proper model configuration."""
        print("🤖 Testing HTCondor agent model configuration...")
        
        # Check that the agent has a model
        assert hasattr(root_agent, 'model'), "Agent should have a model"
        
        # Check model name
        model_name = getattr(root_agent.model, 'model', None)
        if model_name:
            print(f"📊 Agent model: {model_name}")
            assert "gemini" in model_name.lower(), f"Expected Gemini model, got {model_name}"
        
        print("✅ Agent model is properly configured")
    
    @pytest.mark.asyncio
    async def test_htcondor_agent_instructions(self):
        """Test that HTCondor agent has proper instructions."""
        print("📝 Testing HTCondor agent instructions...")
        
        # Check that the agent has instructions
        assert hasattr(root_agent, 'instruction'), "Agent should have instructions"
        assert root_agent.instruction is not None, "Agent instructions should not be None"
        assert len(root_agent.instruction) > 0, "Agent instructions should not be empty"
        
        # Check for HTCondor-specific content in instructions
        instruction_text = root_agent.instruction.lower()
        assert "htcondor" in instruction_text, "Instructions should mention HTCondor"
        assert "job" in instruction_text, "Instructions should mention job management"
        
        print("✅ Agent instructions are properly configured")

if __name__ == "__main__":
    # Run the tests
    pytest.main([__file__, "-v"]) 