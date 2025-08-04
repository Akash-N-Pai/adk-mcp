"""
Custom evaluator for HTCondor MCP agent that checks both trajectory and output quality.
Uses context-aware evaluation with semantic understanding rather than exact word matching.
"""

import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Tuple

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


class SemanticEvaluator:
    """Helper class for semantic similarity and context-aware evaluation."""
    
    @staticmethod
    def similarity_score(text1: str, text2: str) -> float:
        """Calculate similarity between two texts using sequence matching."""
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    @staticmethod
    def contains_semantic_pattern(text: str, patterns: List[str], threshold: float = 0.6) -> bool:
        """Check if text contains any of the semantic patterns."""
        text_lower = text.lower()
        for pattern in patterns:
            if pattern.lower() in text_lower:
                return True
            # Check for semantic similarity
            if SemanticEvaluator.similarity_score(text, pattern) >= threshold:
                return True
        return False
    
    @staticmethod
    def extract_context_indicators(text: str) -> Dict[str, Any]:
        """Extract context indicators from text for intelligent evaluation."""
        text_lower = text.lower()
        
        indicators = {
            "has_job_data": False,
            "has_session_info": False,
            "has_table_format": False,
            "has_status_info": False,
            "has_tool_listing": False,
            "has_error_handling": False,
            "has_helpful_guidance": False,
            "response_type": "unknown",
            "word_count": len(text.split()),
            "has_structure": False
        }
        
        # Job data indicators
        job_patterns = ["cluster", "job", "owner", "procid", "clusterid", "queue", "submit"]
        if any(pattern in text_lower for pattern in job_patterns):
            indicators["has_job_data"] = True
        
        # Session management indicators
        session_patterns = ["session", "previous", "continue", "fresh", "started", "would you like"]
        if any(pattern in text_lower for pattern in session_patterns):
            indicators["has_session_info"] = True
        
        # Table format indicators
        if "|" in text and any(header in text_lower for header in ["clusterid", "procid", "status", "owner"]):
            indicators["has_table_format"] = True
        
        # Status information indicators
        status_patterns = ["running", "idle", "held", "completed", "removed", "status"]
        if any(pattern in text_lower for pattern in status_patterns):
            indicators["has_status_info"] = True
        
        # Tool listing indicators
        tool_patterns = ["basic job management", "tools organized", "available htcondor", "list_jobs", "get_job_status"]
        if any(pattern in text_lower for pattern in tool_patterns):
            indicators["has_tool_listing"] = True
        
        # Error handling indicators
        error_patterns = ["error", "not found", "failed", "invalid", "no jobs", "empty"]
        if any(pattern in text_lower for pattern in error_patterns):
            indicators["has_error_handling"] = True
        
        # Helpful guidance indicators
        guidance_patterns = ["you can", "to check", "use", "cluster id", "do you want", "would you like"]
        if any(pattern in text_lower for pattern in guidance_patterns):
            indicators["has_helpful_guidance"] = True
        
        # Structure indicators
        structure_patterns = ["**", "-", "•", "1.", "2.", ":", "|"]
        if any(pattern in text for pattern in structure_patterns):
            indicators["has_structure"] = True
        
        # Determine response type
        if indicators["has_table_format"] and indicators["has_job_data"]:
            indicators["response_type"] = "job_listing"
        elif indicators["has_tool_listing"]:
            indicators["response_type"] = "tool_listing"
        elif indicators["has_session_info"]:
            indicators["response_type"] = "session_management"
        elif indicators["has_status_info"] and indicators["has_job_data"]:
            indicators["response_type"] = "job_status"
        elif indicators["has_error_handling"]:
            indicators["response_type"] = "error_response"
        else:
            indicators["response_type"] = "general"
        
        return indicators


class HTCondorTrajectoryEvaluator:
    """Evaluates if the agent followed the expected tool usage path with context awareness."""
    
    def evaluate_trajectory(self, expected_tools: List[str], actual_tool_calls: List[Dict]) -> EvaluationResult:
        """
        Evaluate if the agent used the expected tools in the right order.
        Uses context-aware evaluation with flexible matching.
        
        Args:
            expected_tools: List of expected tool names in order
            actual_tool_calls: List of actual tool calls made by agent
        """
        actual_tools = [call.get('name', '') for call in actual_tool_calls]
        comments = []
        score = 0.0
        
        # Tool mapping for flexible matching
        tool_equivalents = {
            "list_jobs": ["list_jobs", "list_htcondor_jobs"],
            "get_job_status": ["get_job_status", "job_status"],
            "list_htcondor_tools": ["list_htcondor_tools", "list_tools", "show_tools"],
            "get_job_history": ["get_job_history", "job_history"],
            "generate_job_report": ["generate_job_report", "job_report"],
            "get_utilization_stats": ["get_utilization_stats", "utilization_stats"],
            "list_user_sessions": ["list_user_sessions", "sessions"],
            "start_fresh_session": ["start_fresh_session", "new_session", "fresh_session"]
        }
        
        # Check if all expected tools were used (with flexible matching)
        expected_used = True
        missing_tools = []
        
        for expected_tool in expected_tools:
            tool_found = False
            # Check exact match
            if expected_tool in actual_tools:
                tool_found = True
            else:
                # Check equivalent tools
                equivalents = tool_equivalents.get(expected_tool, [])
                for equivalent in equivalents:
                    if equivalent in actual_tools:
                        tool_found = True
                        break
            
            if not tool_found:
                expected_used = False
                missing_tools.append(expected_tool)
        
        if expected_used:
            score += 0.5
            comments.append("✅ All expected tools used")
        else:
            comments.append(f"❌ Missing tools: {missing_tools}")
        
        # Check if tools were used in correct order (more flexible)
        if len(expected_tools) > 1:
            expected_order = expected_tools
            actual_order = []
            
            # Map actual tools to expected tools for order checking
            for actual_tool in actual_tools:
                for expected_tool in expected_tools:
                    if actual_tool == expected_tool or actual_tool in tool_equivalents.get(expected_tool, []):
                        actual_order.append(expected_tool)
                        break
            
            if actual_order == expected_order:
                score += 0.3
                comments.append("✅ Tools used in correct order")
            elif len(actual_order) >= len(expected_order) * 0.8:  # 80% order accuracy
                score += 0.2
                comments.append("⚠️ Tools used in mostly correct order")
            else:
                comments.append(f"⚠️ Tools used in wrong order. Expected: {expected_order}, Got: {actual_order}")
        
        # Check for extra/unnecessary tools (context-aware)
        extra_tools = [tool for tool in actual_tools if tool not in expected_tools]
        
        # Special handling for session management tools - these are often used together
        session_tools = ["list_user_sessions", "continue_last_session", "start_fresh_session", "continue_specific_session"]
        session_related_extras = [tool for tool in extra_tools if tool in session_tools]
        other_extras = [tool for tool in extra_tools if tool not in session_tools]
        
        if session_related_extras and not other_extras:
            # Only session-related extras - this is often correct behavior
            comments.append(f"✅ Session management extras (acceptable): {session_related_extras}")
            score += 0.2  # Full points for session management
        elif len(extra_tools) <= 2:  # Allow a few extra tools
            comments.append(f"⚠️ Minor extra tools used: {extra_tools}")
            score += 0.1  # Small penalty but not failure
        elif extra_tools:
            comments.append(f"⚠️ Extra tools used: {extra_tools}")
            score += 0.05  # Small penalty
        else:
            score += 0.2
            comments.append("✅ No unnecessary tools used")
        
        passed = score >= 0.7  # Stricter threshold
        
        return EvaluationResult(
            passed=passed,
            score=score,
            comment=" ".join(comments)
        )


class HTCondorOutputEvaluator(FinalOutputEvaluator):
    """Evaluates the quality of the agent's final response using context-aware criteria."""
    
    def evaluate(self, expected: str, actual: str) -> EvaluationResult:
        """
        Evaluate the quality of the agent's response using semantic understanding.
        
        Args:
            expected: Expected response (can be partial or guidelines)
            actual: Actual agent response
        """
        comments = []
        score = 0.0
        
        # Extract context indicators
        indicators = SemanticEvaluator.extract_context_indicators(actual)
        
        # Context-aware scoring based on response type
        if indicators["response_type"] == "job_listing":
            score += self._evaluate_job_listing(actual, indicators, comments)
        elif indicators["response_type"] == "tool_listing":
            score += self._evaluate_tool_listing(actual, indicators, comments)
        elif indicators["response_type"] == "session_management":
            score += self._evaluate_session_management(actual, indicators, comments)
        elif indicators["response_type"] == "job_status":
            score += self._evaluate_job_status(actual, indicators, comments)
        elif indicators["response_type"] == "error_response":
            score += self._evaluate_error_response(actual, indicators, comments)
        else:
            score += self._evaluate_general_response(actual, indicators, comments)
        
        # Semantic similarity with expected output
        if expected and actual:
            similarity = SemanticEvaluator.similarity_score(expected, actual)
            if similarity >= 0.7:
                score += 0.2
                comments.append("✅ High semantic similarity to expected")
            elif similarity >= 0.5:
                score += 0.1
                comments.append("✅ Moderate semantic similarity to expected")
            else:
                comments.append("⚠️ Low semantic similarity to expected")
        
        # Response length evaluation (context-aware)
        word_count = indicators["word_count"]
        if indicators["response_type"] == "job_listing" and word_count >= 20:
            score += 0.1
            comments.append("✅ Appropriate length for job listing")
        elif indicators["response_type"] == "tool_listing" and word_count >= 30:
            score += 0.1
            comments.append("✅ Appropriate length for tool listing")
        elif indicators["response_type"] == "session_management" and 10 <= word_count <= 50:
            score += 0.1
            comments.append("✅ Appropriate length for session management")
        elif 10 <= word_count <= 200:
            score += 0.1
            comments.append("✅ Appropriate response length")
        elif word_count < 10:
            comments.append("⚠️ Response too brief")
        else:
            comments.append("⚠️ Response too verbose")
        
        passed = score >= 0.6  # Stricter threshold
        
        return EvaluationResult(
            passed=passed,
            score=score,
            comment=" ".join(comments)
        )
    
    def _evaluate_job_listing(self, actual: str, indicators: Dict, comments: List[str]) -> float:
        """Evaluate job listing responses."""
        score = 0.0
        
        if indicators["has_table_format"]:
            score += 0.3
            comments.append("✅ Proper table format for job listing")
        
        if indicators["has_job_data"]:
            score += 0.2
            comments.append("✅ Contains job information")
        
        if indicators["has_status_info"]:
            score += 0.2
            comments.append("✅ Contains status information")
        
        if indicators["has_structure"]:
            score += 0.15
            comments.append("✅ Well-structured job listing")
        
        if indicators["has_helpful_guidance"]:
            score += 0.15
            comments.append("✅ Provides helpful guidance")
        
        return score
    
    def _evaluate_tool_listing(self, actual: str, indicators: Dict, comments: List[str]) -> float:
        """Evaluate tool listing responses."""
        score = 0.0
        
        if indicators["has_tool_listing"]:
            score += 0.3
            comments.append("✅ Proper tool listing format")
        
        if indicators["has_structure"]:
            score += 0.25
            comments.append("✅ Well-structured tool categories")
        
        if indicators["has_helpful_guidance"]:
            score += 0.2
            comments.append("✅ Provides helpful guidance")
        
        if indicators["word_count"] >= 30:
            score += 0.15
            comments.append("✅ Comprehensive tool listing")
        
        return score
    
    def _evaluate_session_management(self, actual: str, indicators: Dict, comments: List[str]) -> float:
        """Evaluate session management responses."""
        score = 0.0
        
        if indicators["has_session_info"]:
            score += 0.4
            comments.append("✅ Contains session management information")
        
        if indicators["has_helpful_guidance"]:
            score += 0.3
            comments.append("✅ Provides session guidance")
        
        if indicators["word_count"] >= 10:
            score += 0.2
            comments.append("✅ Appropriate session response length")
        
        return score
    
    def _evaluate_job_status(self, actual: str, indicators: Dict, comments: List[str]) -> float:
        """Evaluate job status responses."""
        score = 0.0
        
        if indicators["has_job_data"]:
            score += 0.3
            comments.append("✅ Contains job information")
        
        if indicators["has_status_info"]:
            score += 0.3
            comments.append("✅ Contains status information")
        
        if indicators["has_structure"]:
            score += 0.2
            comments.append("✅ Well-structured status response")
        
        if indicators["has_helpful_guidance"]:
            score += 0.2
            comments.append("✅ Provides helpful guidance")
        
        return score
    
    def _evaluate_error_response(self, actual: str, indicators: Dict, comments: List[str]) -> float:
        """Evaluate error handling responses."""
        score = 0.0
        
        if indicators["has_error_handling"]:
            score += 0.4
            comments.append("✅ Proper error handling")
        
        if indicators["has_helpful_guidance"]:
            score += 0.3
            comments.append("✅ Provides helpful error guidance")
        
        if indicators["word_count"] >= 10:
            score += 0.2
            comments.append("✅ Appropriate error response length")
        
        return score
    
    def _evaluate_general_response(self, actual: str, indicators: Dict, comments: List[str]) -> float:
        """Evaluate general responses."""
        score = 0.0
        
        if indicators["has_job_data"]:
            score += 0.2
            comments.append("✅ Contains job information")
        
        if indicators["has_session_info"]:
            score += 0.2
            comments.append("✅ Contains session management information")
        
        if indicators["has_structure"]:
            score += 0.2
            comments.append("✅ Well-structured response")
        
        if indicators["has_helpful_guidance"]:
            score += 0.2
            comments.append("✅ Provides helpful guidance")
        
        if indicators["word_count"] >= 10:
            score += 0.2
            comments.append("✅ Appropriate response length")
        
        return score


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
        Uses context-aware evaluation with semantic understanding.
        
        Returns:
            Dictionary with trajectory_result and output_result
        """
        trajectory_result = self.trajectory_evaluator.evaluate_trajectory(
            expected_tools, actual_tool_calls
        )
        
        output_result = self.output_evaluator.evaluate(
            expected_output, actual_output
        )
        
        # Calculate overall score with context-aware weighting
        overall_score = (trajectory_result.score * 0.6) + (output_result.score * 0.4)
        
        # Stricter passing criteria
        overall_passed = (trajectory_result.score >= 0.6 and output_result.score >= 0.5) and overall_score >= 0.7
        
        return {
            "trajectory": trajectory_result,
            "output": output_result,
            "overall_score": overall_score,
            "overall_passed": overall_passed
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