"""
Streamlined custom evaluator for HTCondor MCP agent.
Essential features only: trajectory evaluation, output evaluation, and basic semantic analysis.
"""

import re
from difflib import SequenceMatcher
from typing import List, Dict, Any, Tuple
from dataclasses import dataclass

# Try different import locations for LangChain evaluation classes
try:
    from langchain.evaluation import FinalOutputEvaluator, EvaluationResult
except ImportError:
    try:
        from langchain.schema import EvaluationResult
        class FinalOutputEvaluator:
            def evaluate(self, expected: str, actual: str) -> EvaluationResult:
                return EvaluationResult(
                    passed=True,
                    score=1.0,
                    comment="Basic evaluation"
                )
    except ImportError:
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
    """Basic semantic similarity and context analysis."""
    
    @staticmethod
    def similarity_score(text1: str, text2: str) -> float:
        """Calculate similarity between two texts."""
        if not text1 or not text2:
            return 0.0
        return SequenceMatcher(None, text1.lower(), text2.lower()).ratio()
    
    @staticmethod
    def extract_context_indicators(text: str) -> Dict[str, Any]:
        """Extract basic context indicators from text."""
        if not text or not isinstance(text, str):
            return {"response_type": "error", "word_count": 0}
        
        text_lower = text.lower()
        words = text.split()
        
        indicators = {
            "has_job_data": False,
            "has_session_info": False,
            "has_table_format": False,
            "has_status_info": False,
            "has_tool_listing": False,
            "has_error_handling": False,
            "has_helpful_guidance": False,
            "response_type": "general",
            "word_count": len(words),
            "has_structure": False
        }
        
        # Basic pattern detection
        job_patterns = ["cluster", "job", "owner", "procid", "clusterid", "queue", "submit"]
        if any(pattern in text_lower for pattern in job_patterns):
            indicators["has_job_data"] = True
        
        session_patterns = ["session", "previous", "continue", "fresh", "started"]
        if any(pattern in text_lower for pattern in session_patterns):
            indicators["has_session_info"] = True
        
        if "|" in text and any(header in text_lower for header in ["clusterid", "procid", "status", "owner"]):
            indicators["has_table_format"] = True
        
        status_patterns = ["running", "idle", "held", "completed", "removed", "status"]
        if any(pattern in text_lower for pattern in status_patterns):
            indicators["has_status_info"] = True
        
        tool_patterns = ["basic job management", "tools organized", "available htcondor"]
        if any(pattern in text_lower for pattern in tool_patterns):
            indicators["has_tool_listing"] = True
        
        error_patterns = ["error", "not found", "failed", "invalid", "no jobs", "empty"]
        if any(pattern in text_lower for pattern in error_patterns):
            indicators["has_error_handling"] = True
        
        guidance_patterns = ["you can", "to check", "use", "cluster id", "do you want"]
        if any(pattern in text_lower for pattern in guidance_patterns):
            indicators["has_helpful_guidance"] = True
        
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
        
        return indicators


class HTCondorTrajectoryEvaluator:
    """Evaluates tool usage trajectory."""
    
    def evaluate_trajectory(self, expected_tools: List[str], actual_tool_calls: List[Dict]) -> EvaluationResult:
        """Evaluate if the agent used expected tools correctly."""
        if not actual_tool_calls:
            return EvaluationResult(passed=False, score=0.0, comment="❌ No tool calls detected")
        
        actual_tools = [call.get('name', '') for call in actual_tool_calls]
        comments = []
        score = 0.0
        
        # Tool equivalents for flexible matching
        tool_equivalents = {
            "list_jobs": ["list_jobs", "list_htcondor_jobs"],
            "get_job_status": ["get_job_status", "job_status"],
            "list_htcondor_tools": ["list_htcondor_tools", "list_tools"],
            "get_job_history": ["get_job_history", "job_history"],
            "generate_job_report": ["generate_job_report", "job_report"],
            "get_utilization_stats": ["get_utilization_stats", "utilization_stats"],
            "list_user_sessions": ["list_user_sessions", "sessions"],
            "start_fresh_session": ["start_fresh_session", "new_session"]
        }
        
        # Check expected tools
        missing_tools = []
        for expected_tool in expected_tools:
            tool_found = False
            if expected_tool in actual_tools:
                tool_found = True
            else:
                equivalents = tool_equivalents.get(expected_tool, [])
                if any(equivalent in actual_tools for equivalent in equivalents):
                    tool_found = True
            
            if not tool_found:
                missing_tools.append(expected_tool)
        
        if not missing_tools:
            score += 0.6
            comments.append("✅ All expected tools used")
        else:
            comments.append(f"❌ Missing tools: {missing_tools}")
        
        # Check for extra tools
        extra_tools = [tool for tool in actual_tools if tool not in expected_tools]
        session_tools = ["list_user_sessions", "continue_last_session", "start_fresh_session"]
        session_extras = [tool for tool in extra_tools if tool in session_tools]
        
        if session_extras and len(extra_tools) == len(session_extras):
            score += 0.2
            comments.append("✅ Session management extras (acceptable)")
        elif len(extra_tools) <= 2:
            score += 0.1
            comments.append(f"⚠️ Minor extra tools: {extra_tools}")
        elif extra_tools:
            comments.append(f"⚠️ Extra tools: {extra_tools}")
        else:
            score += 0.2
            comments.append("✅ No unnecessary tools")
        
        passed = score >= 0.7
        return EvaluationResult(passed=passed, score=score, comment=" ".join(comments))


class HTCondorOutputEvaluator(FinalOutputEvaluator):
    """Evaluates response quality."""
    
    def evaluate(self, expected: str, actual: str) -> EvaluationResult:
        """Evaluate response quality with context awareness."""
        if not actual or not isinstance(actual, str):
            return EvaluationResult(passed=False, score=0.0, comment="❌ Invalid response")
        
        comments = []
        score = 0.0
        
        # Extract context indicators
        indicators = SemanticEvaluator.extract_context_indicators(actual)
        
        # Context-aware scoring
        response_type = indicators["response_type"]
        if response_type == "job_listing":
            score += self._evaluate_job_listing(indicators, comments)
        elif response_type == "tool_listing":
            score += self._evaluate_tool_listing(indicators, comments)
        elif response_type == "session_management":
            score += self._evaluate_session_management(indicators, comments)
        elif response_type == "job_status":
            score += self._evaluate_job_status(indicators, comments)
        elif response_type == "error_response":
            score += self._evaluate_error_response(indicators, comments)
        else:
            score += self._evaluate_general_response(indicators, comments)
        
        # Semantic similarity
        if expected and actual:
            similarity = SemanticEvaluator.similarity_score(expected, actual)
            if similarity >= 0.7:
                score += 0.2
                comments.append("✅ High similarity to expected")
            elif similarity >= 0.5:
                score += 0.1
                comments.append("✅ Moderate similarity to expected")
        
        # Response length
        word_count = indicators["word_count"]
        if 10 <= word_count <= 200:
            score += 0.1
            comments.append("✅ Appropriate length")
        elif word_count < 10:
            comments.append("⚠️ Too brief")
        else:
            comments.append("⚠️ Too verbose")
        
        passed = score >= 0.6
        return EvaluationResult(passed=passed, score=score, comment=" ".join(comments))
    
    def _evaluate_job_listing(self, indicators: Dict, comments: List[str]) -> float:
        score = 0.0
        if indicators["has_table_format"]:
            score += 0.3
            comments.append("✅ Proper table format")
        if indicators["has_job_data"]:
            score += 0.2
            comments.append("✅ Contains job information")
        if indicators["has_status_info"]:
            score += 0.2
            comments.append("✅ Contains status information")
        if indicators["has_structure"]:
            score += 0.15
            comments.append("✅ Well-structured")
        if indicators["has_helpful_guidance"]:
            score += 0.15
            comments.append("✅ Provides guidance")
        return score
    
    def _evaluate_tool_listing(self, indicators: Dict, comments: List[str]) -> float:
        score = 0.0
        if indicators["has_tool_listing"]:
            score += 0.3
            comments.append("✅ Proper tool listing")
        if indicators["has_structure"]:
            score += 0.25
            comments.append("✅ Well-structured categories")
        if indicators["has_helpful_guidance"]:
            score += 0.2
            comments.append("✅ Provides guidance")
        if indicators["word_count"] >= 30:
            score += 0.15
            comments.append("✅ Comprehensive listing")
        return score
    
    def _evaluate_session_management(self, indicators: Dict, comments: List[str]) -> float:
        score = 0.0
        if indicators["has_session_info"]:
            score += 0.4
            comments.append("✅ Contains session information")
        if indicators["has_helpful_guidance"]:
            score += 0.3
            comments.append("✅ Provides session guidance")
        if indicators["word_count"] >= 10:
            score += 0.2
            comments.append("✅ Appropriate length")
        return score
    
    def _evaluate_job_status(self, indicators: Dict, comments: List[str]) -> float:
        score = 0.0
        if indicators["has_job_data"]:
            score += 0.3
            comments.append("✅ Contains job information")
        if indicators["has_status_info"]:
            score += 0.3
            comments.append("✅ Contains status information")
        if indicators["has_structure"]:
            score += 0.2
            comments.append("✅ Well-structured")
        if indicators["has_helpful_guidance"]:
            score += 0.2
            comments.append("✅ Provides guidance")
        return score
    
    def _evaluate_error_response(self, indicators: Dict, comments: List[str]) -> float:
        score = 0.0
        if indicators["has_error_handling"]:
            score += 0.4
            comments.append("✅ Proper error handling")
        if indicators["has_helpful_guidance"]:
            score += 0.3
            comments.append("✅ Provides error guidance")
        if indicators["word_count"] >= 10:
            score += 0.2
            comments.append("✅ Appropriate length")
        return score
    
    def _evaluate_general_response(self, indicators: Dict, comments: List[str]) -> float:
        score = 0.0
        if indicators["has_job_data"]:
            score += 0.2
            comments.append("✅ Contains job information")
        if indicators["has_session_info"]:
            score += 0.2
            comments.append("✅ Contains session information")
        if indicators["has_structure"]:
            score += 0.2
            comments.append("✅ Well-structured")
        if indicators["has_helpful_guidance"]:
            score += 0.2
            comments.append("✅ Provides guidance")
        if indicators["word_count"] >= 10:
            score += 0.2
            comments.append("✅ Appropriate length")
        return score


class HTCondorComprehensiveEvaluator:
    """Combines trajectory and output evaluation."""
    
    def __init__(self):
        self.trajectory_evaluator = HTCondorTrajectoryEvaluator()
        self.output_evaluator = HTCondorOutputEvaluator()
    
    def extract_real_tool_calls(self, response) -> List[Dict]:
        """Extract tool calls from ADK response metadata."""
        tool_calls = []
        
        try:
            # Try to get tool calls from response metadata
            if hasattr(response, 'tool_calls') and response.tool_calls:
                for tool_call in response.tool_calls:
                    tool_calls.append({
                        "name": tool_call.get("name", "unknown"),
                        "args": tool_call.get("arguments", {})
                    })
                return tool_calls
            
            # Fallback to pattern matching
            return self._extract_tool_calls_pattern(response.content if hasattr(response, 'content') else str(response))
            
        except Exception:
            return []
    
    def _extract_tool_calls_pattern(self, response_content: str) -> List[Dict]:
        """Fallback pattern matching for tool calls."""
        tool_calls = []
        response_lower = response_content.lower()
        
        patterns = {
            "list_jobs": ["clusterid", "procid", "status", "owner", "| clusterid |"],
            "list_htcondor_tools": ["basic job management", "tools organized", "available htcondor"],
            "get_job_status": ["cluster id", "status:", "owner:", "command:"],
            "get_job_history": ["job history", "queue date", "job start date"],
            "generate_job_report": ["job report", "report metadata", "total jobs"],
            "get_utilization_stats": ["utilization statistics", "resource utilization"],
            "list_user_sessions": ["previous sessions", "sessions", "session list"],
            "start_fresh_session": ["started", "new session", "fresh session"],
            "continue_last_session": ["continuing", "last session", "resumed session"],
            "continue_specific_session": ["switched to session", "session context"],
            "get_session_history": ["session history", "conversation history"],
            "get_session_summary": ["session summary", "session activities"],
            "get_user_conversation_memory": ["conversation memory", "cross-session"],
            "get_user_context_summary": ["context summary", "user context"],
            "save_job_report": ["saved report", "report saved", "artifact"],
            "load_job_report": ["loaded report", "report loaded"],
            "search_job_memory": ["memory search", "search results"],
            "add_to_memory": ["remembered", "saved to memory"],
            "export_job_data": ["exported", "data export", "csv format"]
        }
        
        for tool_name, tool_patterns in patterns.items():
            if any(pattern in response_lower for pattern in tool_patterns):
                tool_calls.append({"name": tool_name, "args": {}})
        
        return tool_calls
    
    def evaluate(self, 
                expected_tools: List[str],
                actual_tool_calls: List[Dict],
                expected_output: str,
                actual_output: str) -> Dict[str, EvaluationResult]:
        """Comprehensive evaluation combining trajectory and output quality."""
        
        # Extract real tool calls if not provided
        if not actual_tool_calls and hasattr(actual_output, 'tool_calls'):
            actual_tool_calls = self.extract_real_tool_calls(actual_output)
        
        trajectory_result = self.trajectory_evaluator.evaluate_trajectory(
            expected_tools, actual_tool_calls
        )
        
        output_result = self.output_evaluator.evaluate(
            expected_output, actual_output
        )
        
        # Calculate overall score
        overall_score = (trajectory_result.score * 0.6) + (output_result.score * 0.4)
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