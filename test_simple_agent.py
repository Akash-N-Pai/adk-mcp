#!/usr/bin/env python3
"""
Simple test script to verify agent communication works correctly.
"""

import asyncio
import subprocess
import time
import select

async def test_agent_communication():
    """Test basic agent communication."""
    print("🧪 Testing basic agent communication...")
    
    # Start the agent
    print("🚀 Starting agent...")
    agent_process = subprocess.Popen(
        ["adk", "run", "local_mcp/"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        bufsize=1
    )
    
    try:
        # Wait for agent to start
        await asyncio.sleep(3)
        
        # Test first query
        print("📤 Sending: hi")
        agent_process.stdin.write("hi\n")
        agent_process.stdin.flush()
        
        # Wait for response
        await asyncio.sleep(3)
        
        # Read response
        response = ""
        start_time = time.time()
        while time.time() - start_time < 10:
            ready, _, _ = select.select([agent_process.stdout], [], [], 0.1)
            if ready:
                line = agent_process.stdout.readline()
                if line:
                    response += line
                    print(f"📝 Read: {line.strip()}")
                    
                    if "[user]:" in line:
                        print("✅ Found agent prompt")
                        break
            else:
                await asyncio.sleep(0.1)
        
        print(f"📥 Response: {response}")
        
        # Test second query
        print("\n📤 Sending: create a new session")
        agent_process.stdin.write("create a new session\n")
        agent_process.stdin.flush()
        
        # Wait for response
        await asyncio.sleep(3)
        
        # Read response
        response2 = ""
        start_time = time.time()
        while time.time() - start_time < 10:
            ready, _, _ = select.select([agent_process.stdout], [], [], 0.1)
            if ready:
                line = agent_process.stdout.readline()
                if line:
                    response2 += line
                    print(f"📝 Read: {line.strip()}")
                    
                    if "[user]:" in line:
                        print("✅ Found agent prompt")
                        break
            else:
                await asyncio.sleep(0.1)
        
        print(f"📥 Response 2: {response2}")
        
        print("✅ Basic communication test completed")
        
    finally:
        # Clean up
        agent_process.terminate()
        agent_process.wait(timeout=5)

if __name__ == "__main__":
    asyncio.run(test_agent_communication()) 