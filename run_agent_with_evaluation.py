#!/usr/bin/env python3
"""
Simple and robust HTCondor agent evaluation using adk run.
This approach focuses on reliability over complexity.
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

class SimpleADKEvaluator:
    """Simple and robust ADK agent evaluator."""
    
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
            
            # Wait for the agent to start
            time.sleep(5)
            
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
    
    def send_query_and_wait(self, query: str, wait_time: int = 15) -> str:
        """
        Send a query to the agent and wait for a complete response.
        Simple approach: send query, wait fixed time, read all available output.
        """
        try:
            if not self.agent_process or self.agent_process.poll() is not None:
                raise Exception("Agent not running")
            
            print(f"📤 Sending query: {query}")
            
            # Clear any existing output by reading until no more data
            print("🧹 Clearing existing output...")
            while True:
                try:
                    import select
                    ready, _, _ = select.select([self.agent_process.stdout], [], [], 0.1)
                    if ready:
                        line = self.agent_process.stdout.readline()
                        if not line:
                            break
                    else:
                        break
                except:
                    break
            
            # Send the query
            self.agent_process.stdin.write(f"{query}\n")
            self.agent_process.stdin.flush()
            
            # Wait for the agent to process
            print(f"⏳ Waiting {wait_time} seconds for response...")
            time.sleep(wait_time)
            
            # Read all available output
            response_lines = []
            while True:
                try:
                    import select
                    ready, _, _ = select.select([self.agent_process.stdout], [], [], 0.1)
                    if ready:
                        line = self.agent_process.stdout.readline()
                        if line:
                            response_lines.append(line.strip())
                            print(f"📝 {line.strip()}")
                        else:
                            break
                    else:
                        break
                except:
                    break
            
            # Process the response
            response = '\n'.join(response_lines)
            
            # Clean up the response
            cleaned_lines = []
            for line in response_lines:
                # Skip log messages
                if any(skip in line.lower() for skip in [
                    'log setup complete', 'to access latest log', 'running agent', 
                    'type exit to exit', 'tail -f'
                ]):
                    continue
                
                # Clean up agent response format
                if '[htcondor_mcp_client_agent]:' in line:
                    parts = line.split('[htcondor_mcp_client_agent]:')
                    if len(parts) > 1:
                        cleaned_lines.append(parts[1].strip())
                elif line.strip() and not line.startswith('[user]:'):
                    cleaned_lines.append(line)
            
            final_response = '\n'.join(cleaned_lines).strip()
            
            print(f"📥 Response length: {len(final_response)} characters")
            print(f"📄 Response preview: {final_response[:200]}...")
            
            return final_response
            
        except Exception as e:
            print(f"❌ Error communicating with agent: {e}")
            return f"Error: {e}"
    
    def extract_tool_calls(self, query: str, response: str) -> List[Dict]:
        """Extract tool calls from response using simple pattern matching."""
        tool_calls = []
        response_lower = response.lower()
        query_lower = query.lower()
        
        # Simple tool detection based on response content
        if "list all the jobs" in query_lower:
            if any(pattern in response_lower for pattern in [
                "clusterid", "procid", "status", "owner", "jobs from", "total jobs"
            ]):
                tool_calls.append({"name": "list_jobs", "args": {}})
        
        elif "list all the tools" in query_lower:
            if any(pattern in response_lower for pattern in [
                "basic job management", "tools organized", "available htcondor"
            ]):
                tool_calls.append({"name": "list_htcondor_tools", "args": {}})
        
        elif "get job status" in query_lower:
            if any(pattern in response_lower for pattern in [
                "cluster id", "status:", "owner:", "command:"
            ]):
                tool_calls.append({"name": "get_job_status", "args": {}})
        
        elif "get job history" in query_lower:
            if any(pattern in response_lower for pattern in [
                "job history", "queue date", "job start date", "submitted", "started"
            ]):
                tool_calls.append({"name": "get_job_history", "args": {}})
        
        elif "generate job report" in query_lower:
            if any(pattern in response_lower for pattern in [
                "job report", "report metadata", "total jobs", "status distribution"
            ]):
                tool_calls.append({"name": "generate_job_report", "args": {}})
        
        elif "get_utilization_stats" in query_lower:
            if any(pattern in response_lower for pattern in [
                "utilization statistics", "resource utilization", "total jobs", "completed jobs"
            ]):
                tool_calls.append({"name": "get_utilization_stats", "args": {}})
        
        elif "hi" in query_lower:
            if "previous sessions" in response_lower or "sessions" in response_lower:
                tool_calls.append({"name": "list_user_sessions", "args": {}})
        
        elif "create a new session" in query_lower:
            if "started" in response_lower and "session" in response_lower:
                tool_calls.append({"name": "start_fresh_session", "args": {}})
        
        return tool_calls
    
    def test_single_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single case with the running agent."""
        query = test_case["query"]
        expected_tools = test_case["expected_tools"]
        expected_output = test_case["expected_output"]
        
        print(f"\n🧪 Testing: {query}")
        
        try:
            # Get agent response with appropriate wait time
            wait_time = 20 if "list" in query.lower() else 15  # Longer wait for list operations
            response = self.send_query_and_wait(query, wait_time)
            
            print(f"🤖 Agent Response: {response[:100]}...")
            
            # Extract tool calls
            tool_calls = self.extract_tool_calls(query, response)
            print(f"🔧 Tool Calls: {tool_calls}")
            
            # Run evaluation
            print("🔍 Running evaluation...")
            eval_results = self.evaluator.evaluate(
                expected_tools=expected_tools,
                actual_tool_calls=tool_calls,
                expected_output=expected_output,
                actual_output=response
            )
            print("✅ Evaluation completed")
            
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
    
    def run_evaluation_suite(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run evaluation on a suite of test cases."""
        print("🚀 Starting Simple ADK Agent Evaluation Suite")
        print(f"📋 Testing {len(test_cases)} cases...")
        
        # Start the agent
        if not self.start_agent():
            print("❌ Failed to start agent, cannot proceed")
            return []
        
        try:
            self.results = []
            
            for i, test_case in enumerate(test_cases, 1):
                print(f"\n--- Test Case {i}/{len(test_cases)} ---")
                result = self.test_single_case(test_case)
                self.results.append(result)
                
                # Wait between tests
                if i < len(test_cases):
                    print("⏳ Waiting 10 seconds before next test...")
                    time.sleep(10)
            
            return self.results
            
        finally:
            # Always stop the agent
            self.stop_agent()
    
    def generate_report(self, output_file: str = "simple_adk_evaluation_report.json"):
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
        
        print(f"\n📊 SIMPLE ADK EVALUATION SUMMARY")
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
        "name": "Initial Greeting",
        "query": "hi",
        "expected_tools": ["list_user_sessions"],
        "expected_output": "sessions",
        "description": "Agent should greet user and check for existing sessions"
    },
    {
        "name": "Create New Session",
        "query": "create a new session",
        "expected_tools": ["start_fresh_session"],
        "expected_output": "started",
        "description": "Agent should create a new session when requested"
    },
    {
        "name": "List All Jobs",
        "query": "list all the jobs",
        "expected_tools": ["list_jobs"],
        "expected_output": "clusterid",
        "description": "Agent should list jobs in table format"
    },
    {
        "name": "List All Tools",
        "query": "list all the tools",
        "expected_tools": ["list_htcondor_tools"],
        "expected_output": "basic job management",
        "description": "Agent should show organized tool categories"
    },
    {
        "name": "Get Job Status",
        "query": "get job status of 6657640",
        "expected_tools": ["get_job_status"],
        "expected_output": "cluster id",
        "description": "Agent should provide detailed job status information"
    },
    {
        "name": "Get Job History",
        "query": "get job history of 6657640",
        "expected_tools": ["get_job_history"],
        "expected_output": "queue date",
        "description": "Agent should show job execution history"
    },
    {
        "name": "Generate Job Report",
        "query": "generate job report for jareddb2",
        "expected_tools": ["generate_job_report"],
        "expected_output": "job report",
        "description": "Agent should generate comprehensive job report"
    },
    {
        "name": "Get Utilization Stats",
        "query": "get_utilization_stats",
        "expected_tools": ["get_utilization_stats"],
        "expected_output": "utilization",
        "description": "Agent should show system utilization statistics"
    }
]


def main():
    """Main function to run simple ADK agent evaluation."""
    print("🎯 Simple HTCondor MCP Agent Evaluation")
    print("=" * 50)
    
    # Create evaluation runner
    runner = SimpleADKEvaluator()
    
    # Run evaluation suite
    results = runner.run_evaluation_suite(TEST_CASES)
    
    # Generate report
    runner.generate_report()
    
    print("\n✅ Simple ADK evaluation completed!")


if __name__ == "__main__":
    main() 