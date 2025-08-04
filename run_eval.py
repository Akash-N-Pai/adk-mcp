#!/usr/bin/env python3
"""
Simple and robust HTCondor agent evaluation using ADK Runner directly.
Captures full responses by processing agent events.
"""

import json
import asyncio
import time
from typing import List, Dict, Any, Optional

# Import necessary ADK components
from google.adk.agents import Agent
# Assuming your agent definition and tools are available in the environment or can be imported
# For this to work, you need to ensure your agent ('htcondor_mcp_client_agent' or similar),
# its model, description, instruction, tools, and sub_agents are defined
# BEFORE running this evaluation code.
# You might need to copy/paste or import relevant definitions from your agent project.
# For demonstration, I will assume a placeholder for the agent object.
# from your_agent_module import your_htcondor_agent # Example import

from google.adk.runners import Runner # Or InMemoryRunner
from google.adk.sessions import InMemorySessionService # Using In-memory for evaluation simplicity
from google.genai import types # For handling message Content/Parts

# Import the custom evaluator
from custom_evaluator import HTCondorComprehensiveEvaluator

# Define a placeholder for the actual agent object.
# IMPORTANT: Replace this with the actual instantiation of your HTCondor agent
# including its model, description, instruction, tools, and sub_agents.
# You might need to adapt this based on how your agent is structured (e.g., loading from local_mcp/).
# For example:
# from adk.mcp_tool_example.agent import htcondor_mcp_client_agent # Assuming this exists and defines your agent
# ADK_AGENT = htcondor_mcp_client_agent
# OR define it directly here:
# from google.adk.models.lite_llm import LiteLlm # If using LiteLLM
# MODEL_GEMINI_FLASH = "gemini-1.5-flash-latest" # Example model
# ADK_AGENT = Agent(
#     name="htcondor_mcp_client_agent",
#     model=LiteLlm(model=MODEL_GEMINI_FLASH), # Or just MODEL_GEMINI_FLASH if not using LiteLLM
#     description="...", # Your agent's description
#     instruction="...", # Your agent's instruction
#     tools=[...], # Your agent's tools
#     sub_agents=[...], # Your agent's sub_agents if any
# )

# --- Placeholder Agent Definition ---
# Replace this with your actual agent definition.
# This is a minimal example to allow the code structure to run.
# You MUST ensure your actual agent object is available as ADK_AGENT.
try:
    # Attempt to find the agent from a previous cell if it was defined there
    # Or define a placeholder if not found.
    ADK_AGENT = None
    if 'htcondor_mcp_client_agent' in globals():
        print("✨ Found 'htcondor_mcp_client_agent' in globals.")
        ADK_AGENT = globals()['htcondor_mcp_client_agent']
    elif 'root_agent_tool_guardrail' in globals():
         print("✨ Found 'root_agent_tool_guardrail' in globals (using last defined agent as placeholder).")
         ADK_AGENT = globals()['root_agent_tool_guardrail'] # Using the last tutorial agent as placeholder
    else:
        print("⚠️ Agent object not found in globals. Defining a minimal placeholder agent.")
        # Define a very basic placeholder agent if none is found
        from google.adk.models.lite_llm import LiteLlm
        from google.adk.tools.base_tool import BaseTool # Import BaseTool for dummy tool
        class DummyTool(BaseTool): # Define a dummy tool to avoid errors
            name = "dummy_tool"
            description = "A dummy tool."
            def __call__(self, *args, **kwargs):
                return {"result": "dummy"}
        ADK_AGENT = Agent(
            name="placeholder_agent",
            model=LiteLlm(model="gemini-1.5-flash-latest"), # Replace with a valid model if needed
            description="A placeholder agent.",
            instruction="Respond to the user.",
            tools=[DummyTool()],
        )
        print(f"✅ Placeholder agent '{ADK_AGENT.name}' created.")

except Exception as e:
    print(f"❌ Error defining or finding ADK_AGENT: {e}")
    ADK_AGENT = None # Ensure ADK_AGENT is None if definition fails


class SimpleADKEvaluator:
    """Simple and robust ADK agent evaluator using ADK Runner directly."""

    def __init__(self, adk_agent: Agent):
        if not adk_agent:
            raise ValueError("ADK Agent object must be provided.")
        self.adk_agent = adk_agent
        self.evaluator = HTCondorComprehensiveEvaluator()
        self.session_service = InMemorySessionService()
        # Create a runner instance for this evaluation
        self.runner = Runner(
             agent=self.adk_agent,
             app_name="htcondor_evaluation_app", # Unique app name for evaluation
             session_service=self.session_service
        )
        self.user_id = "evaluation_user"
        self.session_id_counter = 0 # Counter for unique session IDs per test case
        self.results = []

    async def create_new_session(self) -> str:
        """Creates a new session for each test case."""
        self.session_id_counter += 1
        session_id = f"evaluation_session_{self.session_id_counter}"
        print(f"\n✨ Creating new session for test case: {session_id}")
        await self.session_service.create_session(
            app_name=self.runner.app_name,
            user_id=self.user_id,
            session_id=session_id
        )
        print(f"✅ Session created: {session_id}")
        return session_id


    async def send_query_and_get_response(self, query: str, session_id: str) -> str:
        """
        Send a query to the agent using runner.run_async and get the complete response.
        """
        print(f"\n📤 Sending query to session {session_id}: {query}")

        # Prepare the user's message in ADK format
        content = types.Content(role='user', parts=[types.Part(text=query)])

        final_response_parts: List[types.Part] = []
        final_response_error: Optional[str] = None
        tool_calls_detected: List[Dict[str, Any]] = [] # To collect tool calls during execution

        try:
            # Use runner.run_async to get events
            # We removed subprocess interaction here.
            async for event in self.runner.run_async(
                user_id=self.user_id,
                session_id=session_id,
                new_message=content
            ):
                # Optional: Print all events for detailed debugging
                # print(f"  [Event] Type: {type(event).__name__}, Final: {event.is_final_response()}, Content: {event.content}, Error: {event.error_message}, Actions: {event.actions}, ToolCalls: {getattr(event, 'tool_calls', 'N/A')}")

                if event.is_final_response():
                    if event.content and event.content.parts:
                        # Collect all parts of the final response
                        final_response_parts.extend(event.content.parts)
                    elif event.actions and event.actions.escalate:
                        final_response_error = event.error_message or 'No specific message.'
                    # Keep iterating until async for loop finishes to ensure all events are processed

                # Capture tool calls explicitly requested by the agent
                # Look for ToolCodeEvent or similar events depending on ADK version/setup
                # This is a simplified detection; may need refinement based on actual event types
                if hasattr(event, 'tool_code') and event.tool_code:
                     # This event indicates tool code generated by the LLM, about to be executed
                     print(f"  [Event] Detected potential tool call code: {event.tool_code}")
                     # Parsing tool calls from raw code requires complex logic.
                     # A simpler approach is to rely on the agent's description/instruction
                     # or look for tool execution results if available in events.
                     # For this simplified evaluator, we'll keep the pattern matching on the FINAL response.
                     # ADK events might include explicit tool_calls in some event types,
                     # but relying on parsing final text is simpler for this example.
                     pass # We will stick to text pattern matching on final response for simplicity

            # Assemble the final response text
            if final_response_parts:
                final_response_text = "".join([part.text for part in final_response_parts if part.text])
            elif final_response_error:
                final_response_text = f"Agent escalated: {final_response_error}"
            else:
                final_response_text = "Agent did not produce a final response." # Default

            print(f"📥 Full Agent Response Captured: {final_response_text}")

            # The tool extraction logic will now run on the *full* captured response text
            return final_response_text

        except Exception as e:
            print(f"❌ Error during agent interaction: {e}")
            return f"Error: {e}"


    def extract_tool_calls(self, query: str, response: str) -> List[Dict]:
        """Extract tool calls from response using simple pattern matching."""
        # This logic now runs on the full captured response.
        # Keep the pattern matching logic as is for simplicity.
        # More advanced evaluation might parse ADK events directly for tool call confirmation.
        tool_calls = []
        response_lower = response.lower()
        query_lower = query.lower()

        # Simple tool detection based on response content (refined patterns might be needed)
        # Check for indicators that the agent likely called the tool
        # This is an approximation since we are not parsing tool call events directly here.

        if "list all the jobs" in query_lower:
            # Look for table format or keywords indicating job listing output
            if any(pattern in response_lower for pattern in [
                "clusterid", "procid", "status", "owner", "jobs from", "total jobs", "|" # Check for table pipes
            ]):
                tool_calls.append({"name": "list_jobs", "args": {}}) # Assuming list_jobs tool name

        elif "list all the tools" in query_lower:
            # Look for tool list formatting or keywords
            if any(pattern in response_lower for pattern in [
                "basic job management", "tools organized", "available htcondor", ":" # Tools often listed with colons
            ]):
                tool_calls.append({"name": "list_htcondor_tools", "args": {}}) # Assuming list_htcondor_tools tool name

        elif "get job status" in query_lower:
             # Look for status output keywords
            if any(pattern in response_lower for pattern in [
                "cluster id", "status:", "owner:", "command:", "job status"
            ]):
                tool_calls.append({"name": "get_job_status", "args": {}}) # Assuming get_job_status tool name

        elif "get job history" in query_lower:
            # Look for history output keywords
            if any(pattern in response_lower for pattern in [
                "job history", "queue date", "job start date", "submitted", "started"
            ]):
                tool_calls.append({"name": "get_job_history", "args": {}}) # Assuming get_job_history tool name

        elif "generate job report" in query_lower:
            # Look for report output keywords
            if any(pattern in response_lower for pattern in [
                "job report", "report metadata", "total jobs", "status distribution", "report generated"
            ]):
                tool_calls.append({"name": "generate_job_report", "args": {}}) # Assuming generate_job_report tool name

        elif "get_utilization_stats" in query_lower or "utilization" in query_lower:
            # Look for utilization output keywords
            if any(pattern in response_lower for pattern in [
                "utilization statistics", "resource utilization", "total jobs", "completed jobs", "utilization report"
            ]):
                tool_calls.append({"name": "get_utilization_stats", "args": {}}) # Assuming get_utilization_stats tool name

        # Add checks for other potential tools like sessions management
        # Assuming 'list_user_sessions' is called for "hi"
        elif "hi" in query_lower and "sessions" in response_lower:
             tool_calls.append({"name": "list_user_sessions", "args": {}}) # Assuming list_user_sessions tool name

        # Assuming 'start_fresh_session' is called for "create a new session"
        elif "create a new session" in query_lower and "session for you" in response_lower:
             tool_calls.append({"name": "start_fresh_session", "args": {}}) # Assuming start_fresh_session tool name


        return tool_calls

    async def test_single_case(self, test_case: Dict[str, Any]) -> Dict[str, Any]:
        """Test a single case with the running agent."""
        query = test_case["query"]
        expected_tools = test_case["expected_tools"]
        expected_output = test_case["expected_output"]
        case_name = test_case.get("name", "Unnamed Case")

        print(f"\n🧪 Testing: {case_name} - '{query}'")

        try:
            # Create a new session for this test case
            session_id = await self.create_new_session()

            # Get agent response using the ADK runner
            response = await self.send_query_and_get_response(query, session_id)

            # Tool calls extraction now runs on the full response text
            tool_calls = self.extract_tool_calls(query, response)
            print(f"🔧 Detected Tool Calls based on response content: {tool_calls}")


            # Run evaluation
            print("🔍 Running evaluation...")
            eval_results = self.evaluator.evaluate(
                expected_tools=expected_tools,
                actual_tool_calls=tool_calls, # Use detected tool calls
                expected_output=expected_output,
                actual_output=response # Use the full captured response
            )
            print("✅ Evaluation completed")

            result = {
                "name": case_name,
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
            print(f"❌ Error testing case '{case_name}': {e}")
            return {
                "name": case_name,
                "query": query,
                "error": str(e),
                "trajectory_score": 0.0,
                "output_score": 0.0,
                "overall_score": 0.0,
                "overall_passed": False
            }

    async def run_evaluation_suite(self, test_cases: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Run evaluation on a suite of test cases."""
        if not self.adk_agent:
             print("❌ ADK Agent object is not available. Cannot run evaluation.")
             return []

        print("🚀 Starting Simple ADK Agent Evaluation Suite (Using ADK Runner)")
        print(f"📋 Testing {len(test_cases)} cases...")

        self.results = []

        for i, test_case in enumerate(test_cases, 1):
            print(f"\n--- Test Case {i}/{len(test_cases)} ---")
            # Use await for the async test_single_case function
            result = await self.test_single_case(test_case)
            self.results.append(result)

            # Optional: Add a small delay between test cases if needed
            if i < len(test_cases):
                 await asyncio.sleep(5) # Use asyncio.sleep for async waiting


        return self.results

    def generate_report(self, output_file: str = "simple_adk_evaluation_report.json"):
        """Generate evaluation report."""
        if not self.results:
            print("No results to report")
            return

        # Calculate summary statistics
        total_cases = len(self.results)
        passed_cases = sum(1 for r in self.results if r.get('overall_passed', False))
        # Ensure calculation handles cases where score might be missing (e.g., due to error)
        avg_trajectory = sum(r.get('trajectory_score', 0) for r in self.results) / total_cases if total_cases > 0 else 0
        avg_output = sum(r.get('output_score', 0) for r in self.results) / total_cases if total_cases > 0 else 0
        avg_overall = sum(r.get('overall_score', 0) for r in self.results) / total_cases if total_cases > 0 else 0


        report = {
            "summary": {
                "total_cases": total_cases,
                "passed_cases": passed_cases,
                "failed_cases": total_cases - passed_cases,
                "success_rate": passed_cases / total_cases if total_cases > 0 else 0,
                "average_trajectory_score": avg_trajectory,
                "average_output_score": avg_output,
                "average_overall_score": avg_overall
            },
            "results": self.results
        }

        # Save report
        try:
            with open(output_file, 'w') as f:
                json.dump(report, f, indent=2)
            print(f"\n📊 SIMPLE ADK EVALUATION SUMMARY")
            print(f"Total Cases: {total_cases}")
            print(f"Passed: {passed_cases}")
            print(f"Failed: {total_cases - passed_cases}")
            print(f"Success Rate: {report['summary']['success_rate']:.1%}")
            print(f"Avg Trajectory Score: {avg_trajectory:.3f}")
            print(f"Avg Output Score: {avg_output:.3f}")
            print(f"Avg Overall Score: {avg_overall:.3f}")
            print(f"Report saved to: {output_file}")
        except Exception as e:
            print(f"❌ Error saving report to {output_file}: {e}")



# Test cases
TEST_CASES = [
    {
        "name": "Initial Greeting",
        "query": "hi",
        # Expected tools detection will now rely on keywords in the FULL final response.
        # Refine expected_output patterns based on the actual full response you expect.
        "expected_tools": ["list_user_sessions"],
        "expected_output": "sessions", # Example pattern
        "description": "Agent should greet user and check for existing sessions"
    },
     {
        "name": "Create New Session",
        "query": "create a new session",
        "expected_tools": ["start_fresh_session"],
        "expected_output": "started", # Example pattern
        "description": "Agent should create a new session when requested"
    },
    {
        "name": "List All Jobs (Limit 10)",
        "query": "list all jobs 10", # Modified query to include limit
        "expected_tools": ["list_jobs"],
        # Expecting part of the table structure or keywords
        "expected_output": "clusterid|procid", # Example pattern, check for table header
        "description": "Agent should list jobs with a limit in table format"
    },
     {
        "name": "List All Tools",
        "query": "list all the tools",
        "expected_tools": ["list_htcondor_tools"],
        "expected_output": "tools organized", # Example pattern
        "description": "Agent should show organized tool categories"
    },
    {
        "name": "Get Job Status (ID)",
        "query": "get job status of 6657640",
        "expected_tools": ["get_job_status"],
        "expected_output": "status:", # Example pattern, look for status field
        "description": "Agent should provide detailed job status information for a specific ID"
    },
    {
        "name": "Get Job History (ID)",
        "query": "get job history of 6657640",
        "expected_tools": ["get_job_history"],
        "expected_output": "queue date", # Example pattern
        "description": "Agent should show job execution history for a specific ID"
    },
    {
        "name": "Generate Job Report (Owner)",
        "query": "generate job report for jareddb2",
        "expected_tools": ["generate_job_report"],
        "expected_output": "job report", # Example pattern
        "description": "Agent should generate comprehensive job report for an owner"
    },
    {
        "name": "Get Utilization Stats",
        "query": "get utilization stats", # Adjusted query for clarity
        "expected_tools": ["get_utilization_stats"],
        "expected_output": "utilization statistics", # Example pattern
        "description": "Agent should show system utilization statistics"
    }
]


async def main():
    """Main function to run simple ADK agent evaluation."""
    print("🎯 Simple HTCondor MCP Agent Evaluation (Using ADK Runner)")
    print("=" * 50)

    # IMPORTANT: Ensure ADK_AGENT is correctly defined or loaded before this line.
    if not ADK_AGENT:
        print("\nEvaluation cannot proceed because the ADK_AGENT object is not defined or loaded correctly.")
        return

    # Create evaluation runner
    # Pass the defined ADK_AGENT object
    runner = SimpleADKEvaluator(adk_agent=ADK_AGENT)

    # Run evaluation suite (requires await)
    results = await runner.run_evaluation_suite(TEST_CASES)

    # Generate report
    runner.generate_report()

    print("\n✅ Simple ADK evaluation completed!")


if __name__ == "__main__":
    # This __main__ block is for running as a standalone script using asyncio.run
    # If running in a notebook with a running event loop (like Colab),
    # you might directly 'await main()' or call 'asyncio.run(main())' depending on notebook setup.
    print("Attempting to run main() using asyncio.run()...")
    try:
        asyncio.run(main())
    except Exception as e:
        print(f"An error occurred during evaluation: {e}")
        # Optional: If in a notebook that supports top-level await,
        # you might prefer calling await main() outside the if __name__ == "__main__": block.
        # print("\nAttempting to run main() using await (for notebook environments)...")
        # await main() # Uncomment and move this line outside the if block for notebook execution