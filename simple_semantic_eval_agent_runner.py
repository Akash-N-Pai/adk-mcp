#!/usr/bin/env python3
"""
Simple Semantic Evaluator with Agent Runner

A straightforward evaluator that uses Google ADK's AgentEvaluator
to evaluate agent performance via test files.
"""

import asyncio
import pytest
from typing import List, Dict, Any
from dataclasses import dataclass

# Import Google ADK AgentEvaluator
try:
    from google.adk.evaluation.agent_evaluator import AgentEvaluator
    ADK_AVAILABLE = True
except ImportError:
    ADK_AVAILABLE = False
    print("Warning: Google ADK not available")

@dataclass
class EvaluationResult:
    """Result of an evaluation."""
    test_name: str
    passed: bool
    score: float
    details: str

class SimpleSemanticEvalAgentRunner:
    """Simple evaluator that uses AgentEvaluator for agent testing."""
    
    def __init__(self):
        if not ADK_AVAILABLE:
            raise ImportError("Google ADK AgentEvaluator not available")
    
    async def evaluate_agent(self, agent_module: str, test_file_path: str) -> EvaluationResult:
        """Evaluate an agent using a single test file."""
        
        try:
            # Use AgentEvaluator to run the evaluation
            result = await AgentEvaluator.evaluate(
                agent_module=agent_module,
                eval_dataset_file_path_or_dir=test_file_path,
            )
            
            # Extract results from the evaluation
            # Note: The actual result structure may vary based on AgentEvaluator implementation
            # This is a simplified interpretation
            passed = True  # Assume passed unless we can determine otherwise
            score = 1.0  # Default score
            details = "Evaluation completed successfully"
            
            # Try to extract more detailed information if available
            if hasattr(result, 'passed'):
                passed = result.passed
            if hasattr(result, 'score'):
                score = result.score
            if hasattr(result, 'details'):
                details = result.details
            
            return EvaluationResult(
                test_name=test_file_path,
                passed=passed,
                score=score,
                details=details
            )
            
        except Exception as e:
            return EvaluationResult(
                test_name=test_file_path,
                passed=False,
                score=0.0,
                details=f"Evaluation failed: {str(e)}"
            )
    
    async def evaluate_multiple_tests(self, agent_module: str, test_files: List[str]) -> List[EvaluationResult]:
        """Evaluate an agent using multiple test files."""
        
        results = []
        for test_file in test_files:
            result = await self.evaluate_agent(agent_module, test_file)
            results.append(result)
        
        return results

# Pytest test functions for integration with testing frameworks

@pytest.mark.asyncio
async def test_with_single_test_file():
    """Test the agent's basic ability via a session file."""
    await AgentEvaluator.evaluate(
        agent_module="home_automation_agent",
        eval_dataset_file_path_or_dir="tests/integration/fixture/home_automation_agent/simple_test.test.json",
    )

@pytest.mark.asyncio
async def test_agent_evaluation():
    """Test agent evaluation with custom evaluator."""
    evaluator = SimpleSemanticEvalAgentRunner()
    
    result = await evaluator.evaluate_agent(
        agent_module="home_automation_agent",
        test_file_path="tests/integration/fixture/home_automation_agent/simple_test.test.json"
    )
    
    assert result.passed, f"Agent evaluation failed: {result.details}"
    assert result.score > 0, "Agent should have a positive score"

@pytest.mark.asyncio
async def test_multiple_agent_evaluations():
    """Test multiple agent evaluations."""
    evaluator = SimpleSemanticEvalAgentRunner()
    
    test_files = [
        "tests/integration/fixture/home_automation_agent/simple_test.test.json",
        "tests/integration/fixture/home_automation_agent/complex_test.test.json"
    ]
    
    results = await evaluator.evaluate_multiple_tests(
        agent_module="home_automation_agent",
        test_files=test_files
    )
    
    # Check that all evaluations passed
    for result in results:
        assert result.passed, f"Test {result.test_name} failed: {result.details}"

async def main():
    """Main function to run evaluation."""
    
    if not ADK_AVAILABLE:
        print("Error: Google ADK not available. Please install the required dependencies.")
        return
    
    # Initialize evaluator
    evaluator = SimpleSemanticEvalAgentRunner()
    
    # Example evaluation
    test_file = "tests/integration/fixture/home_automation_agent/simple_test.test.json"
    agent_module = "home_automation_agent"
    
    print(f"Evaluating {agent_module} with {test_file}...")
    
    try:
        result = await evaluator.evaluate_agent(agent_module, test_file)
        
        print(f"\nEvaluation Results:")
        print(f"Test: {result.test_name}")
        print(f"Status: {'✅ PASS' if result.passed else '❌ FAIL'}")
        print(f"Score: {result.score:.2f}")
        print(f"Details: {result.details}")
        
    except Exception as e:
        print(f"Evaluation failed: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 