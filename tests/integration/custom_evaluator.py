"""
Custom evaluator for HTCondor MCP agent that checks both trajectory and output quality.
"""

# Try different import locations for LangChain evaluation classes
try:
    from langchain.evaluation import FinalOutputEvaluator, EvaluationResult
except ImportError:
    try:
        from langchain.schema import EvaluationResult
        # Create a simple FinalOutputEvaluator if not available
        class FinalOutputEvaluator:
            def evaluate(self, expected: str, actual: str) -> EvaluationResult:
                return EvaluationResult(
                    passed=True,
                    score=1.0,
                    comment="Basic evaluation"
                )
    except ImportError:
        # Fallback: Create our own simple evaluation classes
        from dataclasses import dataclass
        from typing import Optional
        
        @dataclass
        class EvaluationResult:
            passed: bool
            score: float
            comment: str
        
        class FinalOutputEvaluator:
            def evaluate(self, expected: str, actual: str) -> EvaluationResult:
                return EvaluationResult(
                    passed=True,
                    score=1.0,
                    comment="Basic evaluation"
                )

from typing import List, Dict, Any


class HTCondorTrajectoryEvaluator:
    """Evaluates if the agent followed the expected tool usage path."""
    
    def evaluate_trajectory(self, expected_tools: List[str], actual_tool_calls: List[Dict]) -> EvaluationResult:
        """
        Evaluate if the agent used the expected tools in the right order.
        
        Args:
            expected_tools: List of expected tool names in order
            actual_tool_calls: List of actual tool calls made by agent
        """
        actual_tools = [call.get('name', '') for call in actual_tool_calls]
        comments = []
        score = 0.0
        
        # Check if all expected tools were used
        expected_used = all(tool in actual_tools for tool in expected_tools)
        if expected_used:
            score += 0.5
            comments.append("✅ All expected tools used")
        else:
            missing = [tool for tool in expected_tools if tool not in actual_tools]
            comments.append(f"❌ Missing tools: {missing}")
        
        # Check if tools were used in correct order
        if len(expected_tools) > 1:
            expected_order = expected_tools
            actual_order = [tool for tool in actual_tools if tool in expected_tools]
            
            if actual_order == expected_order:
                score += 0.3
                comments.append("✅ Tools used in correct order")
            else:
                comments.append(f"⚠️ Tools used in wrong order. Expected: {expected_order}, Got: {actual_order}")
        
        # Check for extra/unnecessary tools
        extra_tools = [tool for tool in actual_tools if tool not in expected_tools]
        if extra_tools:
            comments.append(f"⚠️ Extra tools used: {extra_tools}")
            score += 0.1  # Small penalty but not failure
        else:
            score += 0.1
            comments.append("✅ No unnecessary tools used")
        
        passed = score >= 0.7
        
        return EvaluationResult(
            passed=passed,
            score=score,
            comment=" ".join(comments)
        )


class HTCondorOutputEvaluator(FinalOutputEvaluator):
    """Evaluates the quality of the agent's final response."""
    
    def evaluate(self, expected: str, actual: str) -> EvaluationResult:
        """
        Evaluate the quality of the agent's response.
        
        Args:
            expected: Expected response (can be partial or guidelines)
            actual: Actual agent response
        """
        comments = []
        score = 0.0
        
        # Check for job-related information
        if any(keyword in actual.lower() for keyword in ["cluster", "job", "status", "owner"]):
            score += 0.2
            comments.append("✅ Contains job information")
        
        # Check for proper table format (for job listings)
        if "|" in actual and any(header in actual.lower() for header in ["clusterid", "procid", "status", "owner"]):
            score += 0.2
            comments.append("✅ Proper table format")
        
        # Check for status information
        if any(status in actual.lower() for status in ["running", "idle", "held", "completed", "removed"]):
            score += 0.15
            comments.append("✅ Contains status information")
        
        # Check for clear structure
        if any(marker in actual for marker in ["**", "-", "•", "1.", "2."]):
            score += 0.15
            comments.append("✅ Well-structured response")
        
        # Check response length (not too short, not too long)
        word_count = len(actual.split())
        if 10 <= word_count <= 200:
            score += 0.1
            comments.append("✅ Appropriate response length")
        elif word_count < 10:
            comments.append("⚠️ Response too brief")
        else:
            comments.append("⚠️ Response too verbose")
        
        # Check for error handling
        if any(error_indicator in actual.lower() for error_indicator in ["error", "not found", "failed", "invalid"]):
            if "job not found" in actual.lower() or "error" in actual.lower():
                score += 0.1
                comments.append("✅ Proper error handling")
        
        # Check for helpful information
        if any(helpful in actual.lower() for helpful in ["you can", "to check", "use", "cluster id"]):
            score += 0.1
            comments.append("✅ Provides helpful guidance")
        
        passed = score >= 0.6
        
        return EvaluationResult(
            passed=passed,
            score=score,
            comment=" ".join(comments)
        )


class HTCondorComprehensiveEvaluator:
    """Combines trajectory and output evaluation for comprehensive assessment."""
    
    def __init__(self):
        self.trajectory_evaluator = HTCondorTrajectoryEvaluator()
        self.output_evaluator = HTCondorOutputEvaluator()
    
    def evaluate(self, 
                expected_tools: List[str],
                actual_tool_calls: List[Dict],
                expected_output: str,
                actual_output: str) -> Dict[str, EvaluationResult]:
        """
        Comprehensive evaluation combining trajectory and output quality.
        
        Returns:
            Dictionary with trajectory_result and output_result
        """
        trajectory_result = self.trajectory_evaluator.evaluate_trajectory(
            expected_tools, actual_tool_calls
        )
        
        output_result = self.output_evaluator.evaluate(
            expected_output, actual_output
        )
        
        return {
            "trajectory": trajectory_result,
            "output": output_result,
            "overall_score": (trajectory_result.score * 0.6) + (output_result.score * 0.4),
            "overall_passed": trajectory_result.passed and output_result.passed
        }


# Example usage
if __name__ == "__main__":
    # Example test case
    expected_tools = ["list_jobs"]
    actual_tool_calls = [
        {"name": "list_jobs", "args": {"owner": None, "status": None, "limit": 10}}
    ]
    
    expected_output = "Show jobs in table format with ClusterId, ProcId, Status, Owner"
    actual_output = """
    Here are the jobs in the queue:
    
    | ClusterId | ProcId | Status | Owner |
    |-----------|--------|--------|-------|
    | 1234567   | 0      | Running | alice |
    | 1234568   | 0      | Idle   | bob   |
    
    This shows all jobs currently in the HTCondor queue.
    """
    
    evaluator = HTCondorComprehensiveEvaluator()
    results = evaluator.evaluate(expected_tools, actual_tool_calls, expected_output, actual_output)
    
    print("=== HTCondor Agent Evaluation Results ===")
    print(f"Trajectory Score: {results['trajectory'].score:.2f} - {results['trajectory'].comment}")
    print(f"Output Score: {results['output'].score:.2f} - {results['output'].comment}")
    print(f"Overall Score: {results['overall_score']:.2f}")
    print(f"Overall Passed: {results['overall_passed']}") 