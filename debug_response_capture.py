#!/usr/bin/env python3
"""
Debug script to test response capture and understand what's going wrong.
"""

import subprocess
import time
import select

def test_response_capture():
    """Test response capture with a simple query."""
    
    print("🚀 Starting debug test...")
    
    # Start the agent
    print("📡 Starting HTCondor agent...")
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
    
    # Clear any existing output
    print("🧹 Clearing existing output...")
    while True:
        try:
            ready, _, _ = select.select([agent_process.stdout], [], [], 0.1)
            if ready:
                line = agent_process.stdout.readline()
                if not line:
                    break
                print(f"🧹 Cleared: {line.strip()}")
            else:
                break
        except:
            break
    
    # Send the test query
    query = "list all the jobs"
    print(f"\n📤 Sending query: {query}")
    
    agent_process.stdin.write(f"{query}\n")
    agent_process.stdin.flush()
    
    # Wait a moment for the agent to start processing
    time.sleep(2)
    
    # Read response with detailed logging
    print("\n📖 Reading response with detailed logging...")
    response_lines = []
    read_count = 0
    max_reads = 100
    
    while read_count < max_reads:
        try:
            ready, _, _ = select.select([agent_process.stdout], [], [], 0.1)
            if ready:
                line = agent_process.stdout.readline()
                if line:
                    response_lines.append(line.strip())
                    print(f"📝 [{read_count:03d}] {line.strip()}")
                    read_count = 0  # Reset counter when we get data
                else:
                    read_count += 1
                    print(f"⏳ [{read_count:03d}] Empty line")
            else:
                read_count += 1
                print(f"⏳ [{read_count:03d}] No data available")
                time.sleep(0.1)
        except Exception as e:
            print(f"❌ Error: {e}")
            read_count += 1
    
    # Process the response
    print(f"\n📊 Total lines captured: {len(response_lines)}")
    print("📄 Full response:")
    for i, line in enumerate(response_lines):
        print(f"  [{i:02d}] {line}")
    
    # Check for expected patterns
    response_text = '\n'.join(response_lines).lower()
    print(f"\n🔍 Pattern analysis:")
    print(f"  Contains 'clusterid': {'clusterid' in response_text}")
    print(f"  Contains 'procid': {'procid' in response_text}")
    print(f"  Contains 'status': {'status' in response_text}")
    print(f"  Contains 'owner': {'owner' in response_text}")
    print(f"  Contains 'there are a total of': {'there are a total of' in response_text}")
    print(f"  Contains '|': {'|' in response_text}")
    
    # Clean up
    print("\n🛑 Stopping agent...")
    agent_process.terminate()
    try:
        agent_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        agent_process.kill()
    
    print("✅ Debug test completed")

if __name__ == "__main__":
    test_response_capture() 