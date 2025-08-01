"""
Integration tests for HTCondor MCP agent using ADK evaluation framework.
"""

import pytest
from pathlib import Path

# Try to import ADK evaluation components
try:
    from google.adk.evaluation.agent_evaluator import AgentEvaluator
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    print("Warning: ADK evaluation framework not available")


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK evaluation framework not available")
@pytest.mark.asyncio
async def test_basic_job_listing():
    """Test the agent's basic job listing functionality."""
    await AgentEvaluator.evaluate(
        agent_module="local_mcp",
        eval_dataset_file_path_or_dir="tests/integration/fixture/htcondor_mcp_agent/basic_job_listing.test.json",
    )


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK evaluation framework not available")
@pytest.mark.asyncio
async def test_job_status_query():
    """Test the agent's job status query functionality."""
    await AgentEvaluator.evaluate(
        agent_module="local_mcp",
        eval_dataset_file_path_or_dir="tests/integration/fixture/htcondor_mcp_agent/job_status_query.test.json",
    )


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK evaluation framework not available")
@pytest.mark.asyncio
async def test_job_submission():
    """Test the agent's job submission functionality."""
    await AgentEvaluator.evaluate(
        agent_module="local_mcp",
        eval_dataset_file_path_or_dir="tests/integration/fixture/htcondor_mcp_agent/job_submission.test.json",
    )


@pytest.mark.skipif(not ADK_AVAILABLE, reason="ADK evaluation framework not available")
@pytest.mark.asyncio
async def test_all_evaluations():
    """Test all evaluation scenarios together."""
    fixture_dir = Path("tests/integration/fixture/htcondor_mcp_agent")
    
    # Run all test files in the fixture directory
    await AgentEvaluator.evaluate(
        agent_module="local_mcp",
        eval_dataset_file_path_or_dir=str(fixture_dir),
    )


def test_evaluation_files_exist():
    """Test that all evaluation files exist."""
    fixture_dir = Path("tests/integration/fixture/htcondor_mcp_agent")
    
    expected_files = [
        "basic_job_listing.test.json",
        "job_status_query.test.json", 
        "job_submission.test.json"
    ]
    
    for file_name in expected_files:
        file_path = fixture_dir / file_name
        assert file_path.exists(), f"Evaluation file {file_name} not found"


def test_agent_module_structure():
    """Test that the agent module has the required structure."""
    try:
        from local_mcp import root_agent
        assert root_agent is not None, "root_agent not found in local_mcp module"
        print(f"✅ Agent module structure is correct. Agent type: {type(root_agent)}")
    except ImportError as e:
        pytest.fail(f"Failed to import root_agent: {e}") 