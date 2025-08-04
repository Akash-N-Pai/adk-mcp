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
            clear_attempts = 0
            max_clear_attempts = 50  # Limit buffer clearing to prevent infinite loops
            while clear_attempts < max_clear_attempts:
                    try:
                        import select
                        ready, _, _ = select.select([self.agent_process.stdout], [], [], 0.1)
                        if ready:
                        line = self.agent_process.stdout.readline()
                        if not line:
                            break
                        clear_attempts += 1
                    else:
                        break
                except:
                    break
            print(f"🧹 Cleared {clear_attempts} lines of existing output")
            
            # Send the query
            self.agent_process.stdin.write(f"{query}\n")
            self.agent_process.stdin.flush()
            
            # Wait for the agent to process
            print(f"⏳ Waiting {wait_time} seconds for response...")
            time.sleep(wait_time)
            
            # Read all available output with improved multi-part response handling
            response_lines = []
            max_read_attempts = 300  # Higher limit for complete responses
            read_attempts = 0
            last_data_time = time.time()
            no_data_count = 0
            max_no_data_count = 20  # Allow more no-data periods
            
            print("📖 Reading response data...")
            
            while read_attempts < max_read_attempts:
                try:
                    import select
                    ready, _, _ = select.select([self.agent_process.stdout], [], [], 0.2)
                    if ready:
                        line = self.agent_process.stdout.readline()
                        if line:
                            response_lines.append(line.strip())
                            print(f"📝 {line.strip()}")
                            read_attempts = 0  # Reset counter when we get data
                            no_data_count = 0  # Reset no-data counter
                            last_data_time = time.time()
                                            else:
                            no_data_count += 1
                    else:
                        no_data_count += 1
                        current_time = time.time()
                        
                        # If we haven't received data for a while, check if we have a complete response
                        if current_time - last_data_time > 2.0:  # 2 seconds without data
                            print("⏰ No data for 2 seconds, checking response completeness...")
                            
                            # Check if we have a complete response based on content
                            response_so_far = '\n'.join(response_lines).lower()
                            
                            if "list all the jobs" in query.lower():
                                # Check for complete job listing with table and summary
                                if ("clusterid" in response_so_far and "procid" in response_so_far and 
                                    "status" in response_so_far and "owner" in response_so_far and
                                    "there are a total of" in response_so_far):
                                    print("✅ Job listing appears complete with table and summary")
                                    break
                                elif no_data_count >= max_no_data_count:
                                    print("⚠️ Stopping job listing read - max no-data count reached")
                                    break
                            
                            elif "list all the tools" in query.lower():
                                # Check for complete tool listing with categories
                                if ("basic job management" in response_so_far and 
                                    "session management" in response_so_far):
                                    print("✅ Tool listing appears complete with all categories")
                                    break
                                elif no_data_count >= max_no_data_count:
                                    print("⚠️ Stopping tool listing read - max no-data count reached")
                                    break
                            
                        else:
                            # For other queries, if we have substantial content, consider it complete
                            if len(response_so_far) > 50:
                                print("✅ Response appears complete with substantial content")
                                break
                            elif no_data_count >= max_no_data_count:
                                print("⚠️ Stopping read - max no-data count reached")
                            break
                    
                    if no_data_count >= max_no_data_count:
                        print("✅ No data available after maximum attempts")
                        break
                    time.sleep(0.2)
                    read_attempts += 1
                except Exception as e:
                    print(f"⚠️ Error reading response: {e}")
                    read_attempts += 1
                
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
            
            # Validate response completeness
            query_lower = query.lower()
            response_lower = final_response.lower()
            
            # Check if response appears complete based on query type
            is_complete = self.check_response_completeness(query_lower, response_lower)
            if not is_complete["complete"]:
                print(f"⚠️ WARNING: Response may be incomplete: {is_complete['reason']}")
                print(f"📊 Response length: {len(final_response)} characters")
                print(f"📊 Expected patterns missing: {is_complete['missing_patterns']}")
            
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
    
    def check_response_completeness(self, query_lower: str, response_lower: str) -> Dict[str, Any]:
        """Check if the response appears complete based on query type."""
        missing_patterns = []
        
        if "list all the jobs" in query_lower:
            expected_patterns = ["clusterid", "procid", "status", "owner", "there are a total of"]
            for pattern in expected_patterns:
                if pattern not in response_lower:
                    missing_patterns.append(pattern)
            
            if missing_patterns:
                return {
                    "complete": False,
                    "reason": "Job listing missing table data or summary",
                    "missing_patterns": missing_patterns
                }
        
        elif "list all the tools" in query_lower:
            expected_patterns = ["basic job management", "tools organized", "available htcondor"]
            found_patterns = [p for p in expected_patterns if p in response_lower]
            
            if not found_patterns:
                return {
                    "complete": False,
                    "reason": "Tool listing missing tool categories",
                    "missing_patterns": expected_patterns
                }
        
        elif "get job status" in query_lower:
            expected_patterns = ["cluster id", "status:", "owner:", "command:"]
            for pattern in expected_patterns:
                if pattern not in response_lower:
                    missing_patterns.append(pattern)
            
            if len(missing_patterns) >= 2:  # Allow some flexibility
                return {
                    "complete": False,
                    "reason": "Job status missing key information",
                    "missing_patterns": missing_patterns
                }
        
        elif "get job history" in query_lower:
            expected_patterns = ["job history", "queue date", "job start date", "submitted", "started"]
            found_patterns = [p for p in expected_patterns if p in response_lower]
            
            if not found_patterns:
                return {
                    "complete": False,
                    "reason": "Job history missing history information",
                    "missing_patterns": expected_patterns
                }
        
        elif "generate job report" in query_lower:
            expected_patterns = ["job report", "report metadata", "total jobs", "status distribution"]
            found_patterns = [p for p in expected_patterns if p in response_lower]
            
            if not found_patterns:
                return {
                    "complete": False,
                    "reason": "Job report missing report information",
                    "missing_patterns": expected_patterns
                }
        
        elif "get_utilization_stats" in query_lower:
            expected_patterns = ["utilization", "statistics", "total jobs", "completed jobs"]
            found_patterns = [p for p in expected_patterns if p in response_lower]
            
            if not found_patterns:
                return {
                    "complete": False,
                    "reason": "Utilization stats missing statistics",
                    "missing_patterns": expected_patterns
                }
        
        return {
            "complete": True,
            "reason": "Response appears complete",
            "missing_patterns": []
        }
    
    def validate_response_quality(self, query: str, response: str) -> Dict[str, Any]:
        """Validate that the response is appropriate for the query type."""
        query_lower = query.lower()
        response_lower = response.lower()
        
        # Check for empty or very short responses
        if len(response.strip()) < 10:
            return {"is_valid": False, "reason": "Response too short"}
        
        # Check for error responses
        if "error" in response_lower or "failed" in response_lower:
            return {"is_valid": False, "reason": "Response contains error"}
        
        # Query-specific validation
        if "list all the jobs" in query_lower:
            if "clusterid" not in response_lower or "procid" not in response_lower:
                return {"is_valid": False, "reason": "Job listing missing table data"}
        
        elif "list all the tools" in query_lower:
            if "basic job management" not in response_lower and "tools organized" not in response_lower:
                return {"is_valid": False, "reason": "Tool listing missing tool categories"}
        
        elif "get job status" in query_lower:
            if "cluster id" not in response_lower and "status:" not in response_lower:
                return {"is_valid": False, "reason": "Job status missing status information"}
        
        elif "get job history" in query_lower:
            if "job history" not in response_lower and "queue date" not in response_lower:
                return {"is_valid": False, "reason": "Job history missing history information"}
        
        elif "generate job report" in query_lower:
            if "job report" not in response_lower and "report metadata" not in response_lower:
                return {"is_valid": False, "reason": "Job report missing report information"}
        
        elif "get_utilization_stats" in query_lower:
            if "utilization" not in response_lower and "statistics" not in response_lower:
                return {"is_valid": False, "reason": "Utilization stats missing statistics"}
        
        return {"is_valid": True, "reason": "Response validation passed"}
    
    def test_single_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single case with the running agent."""
        query = test_case["query"]
        expected_tools = test_case["expected_tools"]
        expected_output = test_case["expected_output"]
        
        print(f"\n🧪 Testing: {query}")
        
        try:
            # Get agent response with appropriate wait time
            if "list all the jobs" in query.lower():
                wait_time = 10  # Shorter wait, focus on proper reading
            elif "list all the tools" in query.lower():
                wait_time = 10  # Shorter wait, focus on proper reading
            else:
                wait_time = 8  # Standard wait for other operations
            response = self.send_query_and_wait(query, wait_time)
            
            print(f"🤖 Agent Response: {response[:100]}...")
            
            # Validate response quality before evaluation
            response_quality = self.validate_response_quality(query, response)
            if not response_quality["is_valid"]:
                print(f"❌ Response validation failed: {response_quality['reason']}")
                return {
                    "query": query,
                    "expected_tools": expected_tools,
                    "actual_tool_calls": [],
                    "expected_output": expected_output,
                    "actual_output": response,
                    "trajectory_score": 0.0,
                    "trajectory_comment": f"Response validation failed: {response_quality['reason']}",
                    "output_score": 0.0,
                    "output_comment": f"Response validation failed: {response_quality['reason']}",
                    "overall_score": 0.0,
                    "overall_passed": False
                }
            
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