#!/usr/bin/env python3
"""
Test script to run a single evaluation case and see what's happening.
"""

import sys
import os
import time

# Add the current directory to the path so we can import the evaluation script
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from run_agent_with_evaluation import SimpleADKEvaluator

def test_single_evaluation():
    """Test a single evaluation case to debug the issue."""
    
    print("🧪 Testing single evaluation case...")
    
    # Create evaluation runner
    runner = SimpleADKEvaluator()
    
    try:
        # Start the agent
        print("🚀 Starting agent...")
        runner.start_agent()
        
        # Wait a bit for agent to fully initialize
        print("⏳ Waiting for agent to fully initialize...")
        time.sleep(10)
        
        # Initialize the agent properly
        print("\n👋 Step 1: Greeting the agent...")
        try:
            greeting_response = runner.send_query_and_wait("hi", wait_time=8)
            print(f"📄 Greeting response: {greeting_response[:200]}...")
        except Exception as e:
            print(f"⚠️ Greeting failed: {e}")
            greeting_response = "Greeting failed"
        
        print("\n🆕 Step 2: Creating a new session...")
        try:
            session_response = runner.send_query_and_wait("create a new session", wait_time=8)
            print(f"📄 Session response: {session_response[:200]}...")
        except Exception as e:
            print(f"⚠️ Session creation failed: {e}")
            session_response = "Session creation failed"
        
        # Test case 3: List All Jobs
        test_case = {
            "name": "List All Jobs",
            "query": "list all the jobs",
            "expected_tools": ["list_jobs"],
            "expected_output": "clusterid",
            "description": "Agent should list jobs in table format"
        }
        
        print(f"\n📋 Step 3: Testing: {test_case['name']}")
        print(f"📝 Query: {test_case['query']}")
        print(f"🎯 Expected output: {test_case['expected_output']}")
        
        # Run the test
        result = runner.test_single_case(test_case)
        
        print(f"\n📊 Test Result:")
        print(f"  Passed: {result['passed']}")
        print(f"  Trajectory Score: {result['trajectory_score']:.3f}")
        print(f"  Output Score: {result['output_score']:.3f}")
        print(f"  Overall Score: {result['overall_score']:.3f}")
        
        print(f"\n🔧 Tool Calls Detected:")
        for tool in result['tool_calls']:
            print(f"  - {tool['name']}")
        
        print(f"\n📄 Actual Response (first 500 chars):")
        response = result.get('response', 'No response captured')
        print(response[:500])
        if len(response) > 500:
            print("... (truncated)")
        
        print(f"\n📊 Response Length: {len(response)} characters")
        
        # Check if expected output is in response
        expected_lower = test_case['expected_output'].lower()
        response_lower = response.lower()
        print(f"\n🔍 Expected output '{expected_lower}' in response: {expected_lower in response_lower}")
        
        if expected_lower in response_lower:
            print("✅ Expected output found in response")
        else:
            print("❌ Expected output NOT found in response")
            print(f"📄 Response contains: {response_lower[:200]}...")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Stop the agent
        print("\n🛑 Stopping agent...")
        runner.stop_agent()

if __name__ == "__main__":
    test_single_evaluation() 