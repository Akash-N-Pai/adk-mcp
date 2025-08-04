#!/usr/bin/env python3
"""
Test script to run a single evaluation case and see what's happening.
"""

import sys
import os
import time
import subprocess
import select

def test_single_evaluation():
    """Test a single evaluation case to debug the issue."""
    
    print("🧪 Testing single evaluation case...")
    
    try:
        # Start the agent directly
        print("🚀 Starting HTCondor agent...")
        agent_process = subprocess.Popen(
            ["adk", "run", "local_mcp/"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Wait for agent to start
        time.sleep(5)
        if agent_process.poll() is not None:
            print("❌ Agent failed to start")
            return
        
        print("✅ Agent started successfully")
        
        # Wait a bit for agent to fully initialize
        print("⏳ Waiting for agent to fully initialize...")
        time.sleep(10)
        
        def send_query_and_get_response(query, wait_time=15):
            """Send a query and get the complete response."""
            print(f"📤 Sending query: {query}")
            
            # Clear any existing output
            print("🧹 Clearing existing output...")
            clear_attempts = 0
            while clear_attempts < 20:
                try:
                    ready, _, _ = select.select([agent_process.stdout], [], [], 0.1)
                    if ready:
                        line = agent_process.stdout.readline()
                        if not line:
                            break
                        clear_attempts += 1
                    else:
                        break
                except:
                    break
            print(f"🧹 Cleared {clear_attempts} lines")
            
            # Send the query
            agent_process.stdin.write(f"{query}\n")
            agent_process.stdin.flush()
            
            # Wait for response
            print(f"⏳ Waiting {wait_time} seconds for response...")
            time.sleep(wait_time)
            
            # Read response with timeout
            response_lines = []
            read_attempts = 0
            max_reads = 200
            last_data_time = time.time()
            
            print("📖 Reading response...")
            while read_attempts < max_reads:
                try:
                    ready, _, _ = select.select([agent_process.stdout], [], [], 0.2)
                    if ready:
                        line = agent_process.stdout.readline()
                        if line:
                            response_lines.append(line.strip())
                            print(f"📝 {line.strip()}")
                            read_attempts = 0
                            last_data_time = time.time()
                        else:
                            read_attempts += 1
                    else:
                        read_attempts += 1
                        current_time = time.time()
                        
                        # Check if we have a complete response
                        if current_time - last_data_time > 3.0:
                            response_so_far = '\n'.join(response_lines).lower()
                            
                            # For job listing, check for complete table
                            if "list all the jobs" in query.lower():
                                if ("clusterid" in response_so_far and "procid" in response_so_far and 
                                    "status" in response_so_far and "owner" in response_so_far and
                                    "there are a total of" in response_so_far):
                                    print("✅ Job listing appears complete")
                                    break
                            
                            # For other queries, check for substantial content
                            elif len(response_so_far) > 50:
                                print("✅ Response appears complete")
                                break
                        
                        if read_attempts >= 20:
                            print("⚠️ Stopping read - max attempts reached")
                            break
                        
                        time.sleep(0.2)
                        
                except Exception as e:
                    print(f"⚠️ Error reading: {e}")
                    read_attempts += 1
            
            # Clean up response
            response = '\n'.join(response_lines)
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
            return final_response
        
        # Initialize the agent properly
        print("\n👋 Step 1: Greeting the agent...")
        greeting_response = send_query_and_get_response("hi", wait_time=8)
        print(f"📄 Greeting response: {greeting_response[:200]}...")
        
        print("\n🆕 Step 2: Creating a new session...")
        session_response = send_query_and_get_response("create a new session", wait_time=8)
        print(f"📄 Session response: {session_response[:200]}...")
        
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
        
        # Get the response
        response = send_query_and_get_response(test_case['query'], wait_time=15)
        
        print(f"\n📄 Actual Response (first 500 chars):")
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
        
        # Simple tool detection
        tool_calls = []
        if "list all the jobs" in test_case['query'].lower():
            if any(pattern in response_lower for pattern in [
                "clusterid", "procid", "status", "owner", "jobs from", "total jobs"
            ]):
                tool_calls.append({"name": "list_jobs", "args": {}})
        
        print(f"\n🔧 Tool Calls Detected:")
        for tool in tool_calls:
            print(f"  - {tool['name']}")
        
        # Simple validation
        if "clusterid" in response_lower and "procid" in response_lower:
            print("✅ Response validation: Has table data")
            passed = True
        else:
            print("❌ Response validation: Missing table data")
            passed = False
        
        print(f"\n📊 Test Result:")
        print(f"  Passed: {passed}")
        print(f"  Tool Calls: {len(tool_calls)}")
        
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Stop the agent
        print("\n🛑 Stopping agent...")
        try:
            agent_process.terminate()
            agent_process.wait(timeout=5)
        except:
            agent_process.kill()
        print("✅ Agent stopped")

if __name__ == "__main__":
    test_single_evaluation() 