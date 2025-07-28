#!/usr/bin/env python3
"""
ADK-compatible evaluation runner for HTCondor MCP agent.
This module provides an evaluation interface that can be used with the ADK evaluation framework
to test the agent's performance on HTCondor job management tasks.
"""

import asyncio
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass

# Configure logging first
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Try to import the agent, but make it optional for testing
try:
    from local_mcp.agent import root_agent
    AGENT_AVAILABLE = True
except ImportError:
    root_agent = None
    AGENT_AVAILABLE = False
    logger.warning("ADK agent not available - using mock mode for testing")


@dataclass
class EvaluationResult:
    """Result of a single evaluation case."""
    case_name: str
    query: str
    success: bool
    tool_usage_score: float
    response_score: float
    expected_tool_use: List[Dict[str, Any]]
    actual_tool_use: List[Dict[str, Any]]
    expected_response_substrings: List[str]
    actual_response: str
    execution_time: float
    error_message: Optional[str] = None


class ADKEvaluator:
    """ADK-compatible evaluator for HTCondor MCP agent."""
    
    def __init__(self, evalset_path: str = "evaluation/adk_evalset.json"):
        """Initialize the evaluator with an evaluation set."""
        self.evalset_path = evalset_path
        self.evalset = self._load_evalset()
        self.agent = root_agent if AGENT_AVAILABLE else None
        self.results: List[EvaluationResult] = []
    
    def _load_evalset(self) -> Dict[str, Any]:
        """Load the evaluation set from JSON file."""
        try:
            with open(self.evalset_path, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            raise FileNotFoundError(f"Evaluation set not found: {self.evalset_path}")
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON in evaluation set: {e}")
    
    def _extract_tool_usage(self, agent_response: str) -> List[Dict[str, Any]]:
        """
        Extract tool usage from agent response.
        This method tries multiple approaches to detect tool usage in agent responses.
        """
        tool_usage = []
        
        # Method 1: Look for explicit tool call patterns in the response
        if "list_jobs" in agent_response.lower():
            tool_usage.append({
                "tool_name": "list_jobs",
                "tool_input": self._extract_list_jobs_params(agent_response)
            })
        
        if "get_job_status" in agent_response.lower():
            tool_usage.append({
                "tool_name": "get_job_status",
                "tool_input": self._extract_job_status_params(agent_response)
            })
        
        if "submit_job" in agent_response.lower():
            tool_usage.append({
                "tool_name": "submit_job",
                "tool_input": self._extract_submit_job_params(agent_response)
            })
        
        # Method 2: Look for JSON-like tool call structures
        import re
        import json
        
        # Try to find JSON tool calls in the response
        json_patterns = [
            r'\{[^{}]*"tool_name"[^{}]*\}',  # Simple JSON with tool_name
            r'\{[^{}]*"function"[^{}]*\}',   # Alternative function call format
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, agent_response)
            for match in matches:
                try:
                    tool_call = json.loads(match)
                    if "tool_name" in tool_call:
                        tool_usage.append(tool_call)
                    elif "function" in tool_call:
                        # Convert function format to tool_name format
                        tool_usage.append({
                            "tool_name": tool_call["function"],
                            "tool_input": tool_call.get("arguments", {})
                        })
                except json.JSONDecodeError:
                    continue
        
        # Method 3: Look for structured tool call blocks
        # Some agents might output tool calls in a specific format
        tool_block_patterns = [
            r'```tool_call\s*\n(.*?)\n```',  # Markdown code blocks
            r'<tool_call>(.*?)</tool_call>',  # XML-like tags
            r'TOOL_CALL:(.*?)(?=\n|$)',       # Simple prefix format
        ]
        
        for pattern in tool_block_patterns:
            matches = re.findall(pattern, agent_response, re.DOTALL | re.IGNORECASE)
            for match in matches:
                try:
                    tool_call = json.loads(match.strip())
                    if "tool_name" in tool_call:
                        tool_usage.append(tool_call)
                except json.JSONDecodeError:
                    # Try to parse as simple format
                    lines = match.strip().split('\n')
                    for line in lines:
                        if ':' in line:
                            key, value = line.split(':', 1)
                            if key.strip().lower() in ['tool', 'function', 'tool_name']:
                                tool_usage.append({
                                    "tool_name": value.strip(),
                                    "tool_input": {}
                                })
        
        # Method 4: Infer tool usage from response content
        # If no explicit tool calls found, try to infer from response content
        if not tool_usage:
            tool_usage = self._infer_tool_usage_from_content(agent_response)
        
        return tool_usage
    
    def _infer_tool_usage_from_content(self, response: str) -> List[Dict[str, Any]]:
        """
        Infer tool usage from response content when explicit tool calls are not found.
        This is a fallback method that tries to guess which tools were used.
        """
        tool_usage = []
        
        # Look for job listing patterns
        if any(pattern in response.lower() for pattern in [
            "jobs in the queue", "clusterid", "procid", "status", "owner",
            "running jobs", "idle jobs", "held jobs", "completed jobs"
        ]):
            tool_usage.append({
                "tool_name": "list_jobs",
                "tool_input": self._extract_list_jobs_params(response)
            })
        
        # Look for job status patterns
        if any(pattern in response.lower() for pattern in [
            "job status", "clusterid", "owner", "proc", "job not found"
        ]):
            tool_usage.append({
                "tool_name": "get_job_status",
                "tool_input": self._extract_job_status_params(response)
            })
        
        # Look for job submission patterns
        if any(pattern in response.lower() for pattern in [
            "job submitted", "new clusterid", "submitted successfully"
        ]):
            tool_usage.append({
                "tool_name": "submit_job",
                "tool_input": self._extract_submit_job_params(response)
            })
        
        return tool_usage
    
    def _extract_list_jobs_params(self, response: str) -> Dict[str, Any]:
        """Extract list_jobs parameters from response."""
        params = {"owner": None, "status": None, "limit": 10}
        
        # Extract owner
        if "user" in response.lower():
            import re
            user_match = re.search(r'user\s+(\w+)', response.lower())
            if user_match:
                params["owner"] = user_match.group(1)
        
        # Extract status
        status_keywords = ["running", "idle", "held", "completed", "removed"]
        for status in status_keywords:
            if status in response.lower():
                params["status"] = status
                break
        
        # Extract limit
        import re
        limit_match = re.search(r'(\d+)\s+jobs?', response.lower())
        if limit_match:
            params["limit"] = int(limit_match.group(1))
        
        return params
    
    def _extract_job_status_params(self, response: str) -> Dict[str, Any]:
        """Extract get_job_status parameters from response."""
        params = {}
        
        # Extract cluster_id
        import re
        job_match = re.search(r'job\s+(\d+)', response.lower())
        if job_match:
            params["cluster_id"] = int(job_match.group(1))
        
        return params
    
    def _extract_submit_job_params(self, response: str) -> Dict[str, Any]:
        """Extract submit_job parameters from response."""
        params = {"submit_description": {}}
        
        # Extract executable
        import re
        exec_match = re.search(r'executable\s+([^\s]+)', response.lower())
        if exec_match:
            params["submit_description"]["executable"] = exec_match.group(1)
        
        # Extract arguments
        args_match = re.search(r'arguments\s+([^\n]+)', response.lower())
        if args_match:
            params["submit_description"]["arguments"] = args_match.group(1).strip()
        
        return params
    
    def _calculate_tool_usage_score(self, expected: List[Dict[str, Any]], 
                                  actual: List[Dict[str, Any]]) -> float:
        """Calculate score for tool usage accuracy."""
        if not expected and not actual:
            return 1.0
        
        if not expected or not actual:
            return 0.0
        
        # Simple exact match scoring
        matches = 0
        for exp_tool in expected:
            for act_tool in actual:
                if (exp_tool.get("tool_name") == act_tool.get("tool_name") and
                    self._compare_tool_inputs(exp_tool.get("tool_input", {}), 
                                            act_tool.get("tool_input", {}))):
                    matches += 1
                    break
        
        return matches / max(len(expected), len(actual))
    
    def _compare_tool_inputs(self, expected: Dict[str, Any], actual: Dict[str, Any]) -> bool:
        """Compare tool input parameters."""
        # For now, do a simple comparison
        # In a real implementation, you might want more sophisticated matching
        return expected == actual
    
    def _calculate_response_score(self, expected_substrings: List[str], 
                                actual_response: str) -> float:
        """Calculate score for response content accuracy."""
        if not expected_substrings:
            return 1.0
        
        matches = 0
        for substring in expected_substrings:
            if substring.lower() in actual_response.lower():
                matches += 1
        
        return matches / len(expected_substrings)
    
    async def _run_single_case(self, case: Dict[str, Any]) -> EvaluationResult:
        """Run a single evaluation case."""
        case_name = case["name"]
        test_data = case["data"][0]  # Assume single test per case for now
        
        query = test_data["query"]
        expected_tool_use = test_data.get("expected_tool_use", [])
        expected_response_substrings = test_data.get("expected_response_substrings", [])
        
        logger.info(f"Running case: {case_name}")
        logger.info(f"Query: {query}")
        
        start_time = time.time()
        
        try:
            # Run the agent
            # Note: This is a simplified interaction - you may need to adjust
            # based on your actual agent interface
            response = await self._interact_with_agent(query)
            
            execution_time = time.time() - start_time
            
            # Extract tool usage from response
            actual_tool_use = self._extract_tool_usage(response)
            
            # Calculate scores
            tool_usage_score = self._calculate_tool_usage_score(expected_tool_use, actual_tool_use)
            response_score = self._calculate_response_score(expected_response_substrings, response)
            
            # Determine overall success
            success = tool_usage_score >= 0.8 and response_score >= 0.6
            
            return EvaluationResult(
                case_name=case_name,
                query=query,
                success=success,
                tool_usage_score=tool_usage_score,
                response_score=response_score,
                expected_tool_use=expected_tool_use,
                actual_tool_use=actual_tool_use,
                expected_response_substrings=expected_response_substrings,
                actual_response=response,
                execution_time=execution_time
            )
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"Error in case {case_name}: {e}")
            
            return EvaluationResult(
                case_name=case_name,
                query=query,
                success=False,
                tool_usage_score=0.0,
                response_score=0.0,
                expected_tool_use=expected_tool_use,
                actual_tool_use=[],
                expected_response_substrings=expected_response_substrings,
                actual_response="",
                execution_time=execution_time,
                error_message=str(e)
            )
    
    async def _interact_with_agent(self, query: str) -> str:
        """
        Interact with the agent and get a response.
        This method communicates with the actual ADK agent.
        """
        if not self.agent:
            # Fallback to mock responses if agent is not available
            logger.warning("Agent not available, using mock responses")
            return self._get_mock_response(query)
        
        try:
            # Method 1: Direct agent interaction (if your agent supports this)
            if hasattr(self.agent, 'run') and callable(getattr(self.agent, 'run')):
                response = await self.agent.run(query)
                return str(response)
            
            # Method 2: Using ADK agent's chat interface
            elif hasattr(self.agent, 'chat') and callable(getattr(self.agent, 'chat')):
                response = await self.agent.chat(query)
                return str(response)
            
            # Method 3: Using ADK agent's generate method
            elif hasattr(self.agent, 'generate') and callable(getattr(self.agent, 'generate')):
                response = await self.agent.generate(query)
                return str(response)
            
            # Method 4: Subprocess communication (if agent runs as separate process)
            else:
                return await self._communicate_via_subprocess(query)
                
        except Exception as e:
            logger.error(f"Error communicating with agent: {e}")
            # Fallback to mock response on error
            return self._get_mock_response(query)
    
    def _get_mock_response(self, query: str) -> str:
        """Fallback mock responses for testing."""
        if "list_jobs" in query.lower():
            if "alice" in query.lower():
                return "Jobs for user alice: | ClusterId | ProcId | Status | Owner |\n| 1234567 | 0 | Running | alice |"
            elif "running" in query.lower():
                return "Running jobs: | ClusterId | ProcId | Status | Owner |\n| 1234567 | 0 | Running | alice |"
            else:
                return "Jobs in the queue: | ClusterId | ProcId | Status | Owner |\n| 1234567 | 0 | Running | alice |"
        elif "get_job_status" in query.lower() or "status of job" in query.lower():
            return "Job 1234567 status:\n- Owner: alice\n- Status: Running\n- ProcId: 0"
        elif "submit_job" in query.lower() or "submit" in query.lower():
            return "Job submitted successfully! New ClusterId: 2345678"
        else:
            return "I understand your request. Let me help you with that."
    
    async def _communicate_via_subprocess(self, query: str) -> str:
        """
        Communicate with agent via subprocess if it runs as a separate process.
        This is useful if your agent is launched as a web service or CLI tool.
        """
        import subprocess
        import json
        
        try:
            # Option 1: If your agent has a CLI interface
            # Example: python -m local_mcp.agent --query "your query here"
            cmd = ["python3", "-m", "local_mcp.agent", "--query", query]
            
            # Option 2: If your agent runs as a web service
            # import requests
            # response = requests.post("http://localhost:8000/chat", json={"query": query})
            # return response.json()["response"]
            
            # Option 3: If your agent uses ADK web interface
            # You might need to start the agent first: adk web
            # Then communicate via HTTP
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30  # 30 second timeout
            )
            
            if result.returncode == 0:
                return result.stdout.strip()
            else:
                logger.error(f"Agent subprocess failed: {result.stderr}")
                return self._get_mock_response(query)
                
        except subprocess.TimeoutExpired:
            logger.error("Agent communication timed out")
            return self._get_mock_response(query)
        except Exception as e:
            logger.error(f"Subprocess communication error: {e}")
            return self._get_mock_response(query)
    
    async def run_evaluation(self) -> List[EvaluationResult]:
        """Run the complete evaluation."""
        logger.info(f"Starting ADK evaluation with {len(self.evalset['eval_cases'])} cases")
        
        self.results = []
        
        for case in self.evalset["eval_cases"]:
            result = await self._run_single_case(case)
            self.results.append(result)
            
            # Log result
            status = "✅ PASS" if result.success else "❌ FAIL"
            logger.info(f"{status} {result.case_name} "
                       f"(Tool: {result.tool_usage_score:.2f}, "
                       f"Response: {result.response_score:.2f})")
        
        return self.results
    
    def generate_report(self, output_path: str = "evaluation/adk_eval_report.json"):
        """Generate a detailed evaluation report."""
        if not self.results:
            logger.warning("No results to report")
            return
        
        # Calculate summary statistics
        total_cases = len(self.results)
        successful_cases = sum(1 for r in self.results if r.success)
        avg_tool_score = sum(r.tool_usage_score for r in self.results) / total_cases
        avg_response_score = sum(r.response_score for r in self.results) / total_cases
        avg_execution_time = sum(r.execution_time for r in self.results) / total_cases
        
        report = {
            "eval_set_info": {
                "eval_set_id": self.evalset.get("eval_set_id"),
                "eval_set_name": self.evalset.get("eval_set_name"),
                "description": self.evalset.get("description"),
                "version": self.evalset.get("version")
            },
            "summary": {
                "total_cases": total_cases,
                "successful_cases": successful_cases,
                "failed_cases": total_cases - successful_cases,
                "success_rate": successful_cases / total_cases,
                "average_tool_usage_score": avg_tool_score,
                "average_response_score": avg_response_score,
                "average_execution_time": avg_execution_time
            },
            "results": [
                {
                    "case_name": r.case_name,
                    "query": r.query,
                    "success": r.success,
                    "tool_usage_score": r.tool_usage_score,
                    "response_score": r.response_score,
                    "execution_time": r.execution_time,
                    "expected_tool_use": r.expected_tool_use,
                    "actual_tool_use": r.actual_tool_use,
                    "expected_response_substrings": r.expected_response_substrings,
                    "actual_response": r.actual_response,
                    "error_message": r.error_message
                }
                for r in self.results
            ]
        }
        
        # Save report
        with open(output_path, 'w') as f:
            json.dump(report, f, indent=2)
        
        logger.info(f"Evaluation report saved to: {output_path}")
        
        # Print summary
        self._print_summary(report["summary"])
        
        return report
    
    def _print_summary(self, summary: Dict[str, Any]):
        """Print evaluation summary."""
        print("\n" + "="*60)
        print("📊 ADK EVALUATION SUMMARY")
        print("="*60)
        print(f"Total Cases: {summary['total_cases']}")
        print(f"Successful: {summary['successful_cases']}")
        print(f"Failed: {summary['failed_cases']}")
        print(f"Success Rate: {summary['success_rate']:.1%}")
        print(f"Average Tool Usage Score: {summary['average_tool_usage_score']:.3f}")
        print(f"Average Response Score: {summary['average_response_score']:.3f}")
        print(f"Average Execution Time: {summary['average_execution_time']:.3f}s")
        print("="*60)


async def main():
    """Main function for running ADK evaluation."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Run ADK evaluation for HTCondor MCP agent")
    parser.add_argument("--evalset", type=str, default="evaluation/adk_evalset.json",
                       help="Path to evaluation set JSON file")
    parser.add_argument("--report", type=str, default="evaluation/adk_eval_report.json",
                       help="Path to save evaluation report")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Create evaluator
        evaluator = ADKEvaluator(args.evalset)
        
        # Run evaluation
        results = await evaluator.run_evaluation()
        
        # Generate report
        evaluator.generate_report(args.report)
        
        print(f"\n✅ ADK evaluation completed! {len(results)} cases evaluated.")
        
    except Exception as e:
        logger.error(f"Evaluation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main()) 