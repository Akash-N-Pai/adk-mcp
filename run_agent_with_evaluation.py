#!/usr/bin/env python3
"""
Script to run HTCondor agent with evaluation using adk run.
This approach starts the agent via CLI and then interacts with it.
"""

import asyncio
import json
import subprocess
import time
import sys
import os
from pathlib import Path
from typing import List, Dict, Any

# Import the custom evaluator
from custom_evaluator import HTCondorComprehensiveEvaluator

class ADKAgentEvaluationRunner:
    """Runs evaluation using adk run to start the agent."""
    
    def __init__(self):
        self.evaluator = HTCondorComprehensiveEvaluator()
        self.agent_process = None
        self.results = []
    
    def start_agent(self):
        """Start the agent using adk run."""
        print("🚀 Starting HTCondor agent with adk run...")
        
        try:
            # Start the agent in the background
            self.agent_process = subprocess.Popen(
                ["adk", "run", "local_mcp/"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.PIPE,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Wait a moment for the agent to start
            time.sleep(3)
            
            if self.agent_process.poll() is None:
                print("✅ Agent started successfully")
                return True
            else:
                print("❌ Agent failed to start")
                return False
                
        except Exception as e:
            print(f"❌ Failed to start agent: {e}")
            return False
    
    def stop_agent(self):
        """Stop the agent process."""
        if self.agent_process:
            print("🛑 Stopping agent...")
            self.agent_process.terminate()
            try:
                self.agent_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.agent_process.kill()
            print("✅ Agent stopped")
    
    async def send_query_to_agent(self, query: str) -> str:
        """Send a query to the running agent and get response."""
        try:
            if not self.agent_process or self.agent_process.poll() is not None:
                raise Exception("Agent not running")
            
            # Send the query to the agent
            print(f"📤 Sending query: {query[:50]}...")
            
            # Write query to agent's stdin
            self.agent_process.stdin.write(query + "\n")
            self.agent_process.stdin.flush()
            
            # Read response from stdout
            response = ""
            timeout = 30  # 30 second timeout
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                if self.agent_process.stdout.readable():
                    line = self.agent_process.stdout.readline()
                    if line:
                        response += line
                        # Check if response is complete (look for end markers)
                        if "Assistant:" in line or "Human:" in line or not line.strip():
                            break
                    else:
                        time.sleep(0.1)
                else:
                    time.sleep(0.1)
            
            if not response.strip():
                # Fallback: try to get any available output
                response = "No response received from agent"
            
            print(f"📥 Received response: {len(response)} characters")
            return response
            
        except Exception as e:
            print(f"❌ Error communicating with agent: {e}")
            return f"Error: {str(e)}"
    
    async def test_single_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single case with the running agent."""
        query = test_case["query"]
        expected_tools = test_case["expected_tools"]
        expected_output = test_case["expected_output"]
        
        print(f"\n🧪 Testing: {query}")
        
        try:
            # Get agent response
            response = await self.send_query_to_agent(query)
            
            print(f"🤖 Agent Response: {response[:100]}...")
            
            # Extract tool calls from response
            tool_calls = await self._extract_tool_calls(query, response)
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
    
    async def _extract_tool_calls(self, query: str, response: str) -> List[Dict]:
        """Extract tool calls from agent response."""
        tool_calls = []
        response_lower = response.lower()
        query_lower = query.lower()
        
        # Enhanced tool detection based on response patterns
        tool_patterns = {
            "list_htcondor_tools": ["list_htcondor_tools", "available htcondor", "tools organized by category"],
            "list_jobs": ["list_jobs", "clusterid", "procid", "status", "owner", "jobs from a total"],
            "get_job_status": ["get_job_status", "cluster id:", "status:", "owner:", "command:"],
            "submit_job": ["submit_job", "job submitted", "cluster id"],
            "get_job_history": ["get_job_history", "job history", "job submitted", "job started"],
            "generate_job_report": ["generate_job_report", "job report for", "report metadata"],
            "get_utilization_stats": ["get_utilization_stats", "utilization statistics", "resource utilization"],
            "export_job_data": ["export_job_data", "exported data", "csv format"],
            "save_job_report": ["save_job_report", "saved a comprehensive report", "artifact id"],
            "load_job_report": ["load_job_report", "loaded your previously saved", "report details"],
            "search_job_memory": ["search_job_memory", "found the following information", "in your memory"],
            "get_user_context_summary": ["get_user_context_summary", "comprehensive context summary", "user context"],
            "add_to_memory": ["add_to_memory", "saved your preference", "added to your user memory"],
            "list_user_sessions": ["list_user_sessions", "previous sessions", "would you like to continue"],
            "continue_last_session": ["continue_last_session", "continuing your last session", "were working with"],
            "continue_specific_session": ["continue_specific_session", "switched to session", "session summary"],
            "start_fresh_session": ["start_fresh_session", "started a fresh session", "new session"],
            "get_session_history": ["get_session_history", "session history", "conversation history"],
            "get_session_summary": ["get_session_summary", "session summary", "tools used"],
            "get_user_conversation_memory": ["get_user_conversation_memory", "conversation memory", "across all sessions"]
        }
        
        # Check for tool usage patterns in response
        for tool_name, patterns in tool_patterns.items():
            if any(pattern in response_lower for pattern in patterns):
                tool_calls.append({"name": tool_name, "args": {}})
        
        # Remove duplicates while preserving order
        seen = set()
        unique_tool_calls = []
        for tool_call in tool_calls:
            if tool_call["name"] not in seen:
                seen.add(tool_call["name"])
                unique_tool_calls.append(tool_call)
        
        return unique_tool_calls
    
    async def run_evaluation_suite(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run evaluation on a suite of test cases."""
        print("🚀 Starting ADK Agent Evaluation Suite")
        print(f"📋 Testing {len(test_cases)} cases...")
        
        # Start the agent
        if not self.start_agent():
            print("❌ Failed to start agent, cannot proceed")
            return []
        
        try:
            self.results = []
            
            for i, test_case in enumerate(test_cases, 1):
                print(f"\n--- Test Case {i}/{len(test_cases)} ---")
                result = await self.test_single_case(test_case)
                self.results.append(result)
                
                # Small delay between tests
                await asyncio.sleep(1)
            
            return self.results
            
        finally:
            # Always stop the agent
            self.stop_agent()
    
    def generate_report(self, output_file: str = "adk_evaluation_report.json"):
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
        
        print(f"\n📊 ADK EVALUATION SUMMARY")
        print(f"Total Cases: {total_cases}")
        print(f"Passed: {passed_cases}")
        print(f"Failed: {total_cases - passed_cases}")
        print(f"Success Rate: {passed_cases/total_cases:.1%}")
        print(f"Avg Trajectory Score: {avg_trajectory:.3f}")
        print(f"Avg Output Score: {avg_output:.3f}")
        print(f"Avg Overall Score: {avg_overall:.3f}")
        print(f"Report saved to: {output_file}")


# Test cases (same as before)
TEST_CASES = [
    {
        "name": "Initial Greeting and Session Management",
        "query": "hi",
        "expected_tools": ["list_user_sessions"],
        "expected_output": "Welcome! I can see you have",
        "description": "Agent should greet user and check for existing sessions"
    },
    {
        "name": "List All Tools",
        "query": "list all the tools",
        "expected_tools": ["list_htcondor_tools"],
        "expected_output": "Basic Job Management",
        "description": "Agent should show organized tool categories"
    },
    {
        "name": "List All Jobs",
        "query": "list all the jobs",
        "expected_tools": ["list_jobs"],
        "expected_output": "ClusterId\tProcId\tStatus\tOwner",
        "description": "Agent should list jobs in table format with proper headers"
    },
    {
        "name": "Get Job Status",
        "query": "get job status of 6657640",
        "expected_tools": ["get_job_status"],
        "expected_output": "Cluster ID: 6657640",
        "description": "Agent should provide detailed job status information"
    }
]


async def main():
    """Main function to run ADK agent evaluation."""
    print("🎯 HTCondor MCP Agent Evaluation with ADK Run")
    print("=" * 55)
    
    # Create evaluation runner
    runner = ADKAgentEvaluationRunner()
    
    # Run evaluation suite
    results = await runner.run_evaluation_suite(TEST_CASES)
    
    # Generate report
    runner.generate_report()
    
    print("\n✅ ADK evaluation completed!")


if __name__ == "__main__":
    asyncio.run(main()) 