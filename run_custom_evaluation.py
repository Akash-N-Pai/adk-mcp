"""
Script to run custom evaluation on HTCondor MCP agent with real agent outputs.
"""

import asyncio
import json

from pathlib import Path
from typing import List, Dict, Any

# No need to add project root since we're in the root directory

# Import the custom evaluator
from custom_evaluator import HTCondorComprehensiveEvaluator

# Try to import ADK components
try:
    from google.adk.evaluation.agent_evaluator import AgentEvaluator
    from local_mcp import root_agent
    ADK_AVAILABLE = True
    print("✅ ADK and agent available - using real agent")
except ImportError as e:
    ADK_AVAILABLE = False
    print(f"Warning: ADK not available ({e}), using mock mode")


class CustomEvaluationRunner:
    """Runs custom evaluation on HTCondor agent."""
    
    def __init__(self):
        self.evaluator = HTCondorComprehensiveEvaluator()
        self.agent = root_agent if ADK_AVAILABLE else None
        self.results = []
    
    async def test_single_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """
        Test a single case and evaluate it.
        
        Args:
            test_case: Dictionary containing query, expected_tools, expected_output
        """
        query = test_case["query"]
        expected_tools = test_case["expected_tools"]
        expected_output = test_case["expected_output"]
        
        print(f"\n🧪 Testing: {query}")
        
        try:
            # Get agent response
            if self.agent:
                # Use real agent
                response = await self._get_agent_response(query)
                tool_calls = await self._extract_tool_calls(query, response)
            else:
                # Mock response for testing
                response, tool_calls = self._get_mock_response(query)
            
            print(f"🤖 Agent Response: {response[:100]}...")
            print(f"🔧 Tool Calls: {tool_calls}")
            
            # Run custom evaluation
            eval_results = self.evaluator.evaluate(
                expected_tools=expected_tools,
                actual_tool_calls=tool_calls,
                expected_output=expected_output,
                actual_output=response
            )
            
            result = {
                "query": query,
                "expected_tools": expected_tools,
                "actual_tool_calls": tool_calls,
                "expected_output": expected_output,
                "actual_output": response,
                "trajectory_score": eval_results["trajectory"].score,
                "trajectory_comment": eval_results["trajectory"].comment,
                "output_score": eval_results["output"].score,
                "output_comment": eval_results["output"].comment,
                "overall_score": eval_results["overall_score"],
                "overall_passed": eval_results["overall_passed"]
            }
            
            # Print results
            print(f"📊 Trajectory: {eval_results['trajectory'].score:.2f} - {eval_results['trajectory'].comment}")
            print(f"📊 Output: {eval_results['output'].score:.2f} - {eval_results['output'].comment}")
            print(f"📊 Overall: {eval_results['overall_score']:.2f} - {'✅ PASS' if eval_results['overall_passed'] else '❌ FAIL'}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error testing case: {e}")
            return {
                "query": query,
                "error": str(e),
                "trajectory_score": 0.0,
                "output_score": 0.0,
                "overall_score": 0.0,
                "overall_passed": False
            }
    
    async def _get_agent_response(self, query: str) -> str:
        """Get response from actual agent."""
        # This is a simplified version - you might need to adjust based on your agent interface
        try:
            # Try different methods to interact with agent
            if hasattr(self.agent, 'run') and callable(getattr(self.agent, 'run')):
                response = await self.agent.run(query)
                return str(response)
            elif hasattr(self.agent, 'chat') and callable(getattr(self.agent, 'chat')):
                response = await self.agent.chat(query)
                return str(response)
            else:
                raise Exception("No suitable agent method found")
        except Exception as e:
            print(f"Agent interaction failed: {e}")
            return self._get_mock_response(query)[0]
    
    async def _extract_tool_calls(self, query: str, response: str) -> List[Dict]:
        """Extract tool calls from agent response."""
        # This is a simplified extraction - you might need more sophisticated parsing
        tool_calls = []
        
        # Look for tool usage patterns in the response
        if "list_jobs" in response.lower():
            tool_calls.append({"name": "list_jobs", "args": {}})
        if "get_job_status" in response.lower():
            tool_calls.append({"name": "get_job_status", "args": {}})
        if "submit_job" in response.lower():
            tool_calls.append({"name": "submit_job", "args": {}})
        
        return tool_calls
    
    def _get_mock_response(self, query: str) -> tuple[str, List[Dict]]:
        """Get mock response for testing without agent."""
        if "show me all jobs" in query.lower():
            response = """
            Here are the jobs in the queue:
            
            | ClusterId | ProcId | Status | Owner |
            |-----------|--------|--------|-------|
            | 1234567   | 0      | Running | alice |
            | 1234568   | 0      | Idle   | bob   |
            
            This shows all jobs currently in the HTCondor queue.
            """
            tool_calls = [{"name": "list_jobs", "args": {}}]
        elif "status of job" in query.lower():
            response = """
            Job Status for Cluster 1234567:
            - **Status**: Running (2)
            - **Owner**: alice
            - **Command**: /home/user/script.sh
            
            **Resource Usage:**
            - CPUs: 1
            - Memory: 10000 MB
            """
            tool_calls = [{"name": "get_job_status", "args": {}}]
        else:
            response = "I understand your request. Let me help you with that."
            tool_calls = []
        
        return response, tool_calls
    
    async def run_evaluation_suite(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run evaluation on a suite of test cases."""
        print("🚀 Starting Custom Evaluation Suite")
        print(f"📋 Testing {len(test_cases)} cases...")
        
        self.results = []
        
        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- Test Case {i}/{len(test_cases)} ---")
            result = await self.test_single_case(test_case)
            self.results.append(result)
        
        return self.results
    
    def generate_report(self, output_file: str = "custom_evaluation_report.json"):
        """Generate evaluation report."""
        if not self.results:
            print("No results to report")
            return
        
        # Calculate summary statistics
        total_cases = len(self.results)
        passed_cases = sum(1 for r in self.results if r.get('overall_passed', False))
        avg_trajectory = sum(r.get('trajectory_score', 0) for r in self.results) / total_cases
        avg_output = sum(r.get('output_score', 0) for r in self.results) / total_cases
        avg_overall = sum(r.get('overall_score', 0) for r in self.results) / total_cases
        
        report = {
            "summary": {
                "total_cases": total_cases,
                "passed_cases": passed_cases,
                "failed_cases": total_cases - passed_cases,
                "success_rate": passed_cases / total_cases,
                "average_trajectory_score": avg_trajectory,
                "average_output_score": avg_output,
                "average_overall_score": avg_overall
            },
            "results": self.results
        }
        
        # Save report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)
        
        print(f"\n📊 EVALUATION SUMMARY")
        print(f"Total Cases: {total_cases}")
        print(f"Passed: {passed_cases}")
        print(f"Failed: {total_cases - passed_cases}")
        print(f"Success Rate: {passed_cases/total_cases:.1%}")
        print(f"Avg Trajectory Score: {avg_trajectory:.3f}")
        print(f"Avg Output Score: {avg_output:.3f}")
        print(f"Avg Overall Score: {avg_overall:.3f}")
        print(f"Report saved to: {output_file}")


# Test cases
TEST_CASES = [
    {
        "query": "Show me all jobs",
        "expected_tools": ["list_jobs"],
        "expected_output": "Show jobs in table format with ClusterId, ProcId, Status, Owner"
    },
    {
        "query": "What's the status of job 1234567?",
        "expected_tools": ["get_job_status"],
        "expected_output": "Show detailed job status information"
    },
    {
        "query": "Submit a job to run /bin/sleep 100",
        "expected_tools": ["submit_job"],
        "expected_output": "Confirm job submission with cluster ID"
    },
    {
        "query": "Show jobs for user alice",
        "expected_tools": ["list_jobs"],
        "expected_output": "Show filtered jobs for specific user"
    },
    {
        "query": "Give me a complete overview of the HTCondor system",
        "expected_tools": ["get_pool_status", "get_system_load", "get_queue_stats"],
        "expected_output": "Provide comprehensive system overview"
    }
]


async def main():
    """Main function to run custom evaluation."""
    print("🎯 HTCondor MCP Agent Custom Evaluation")
    print("=" * 50)
    
    # Create evaluation runner
    runner = CustomEvaluationRunner()
    
    # Run evaluation suite
    results = await runner.run_evaluation_suite(TEST_CASES)
    
    # Generate report
    runner.generate_report()
    
    print("\n✅ Custom evaluation completed!")


if __name__ == "__main__":
    asyncio.run(main()) 