#!/usr/bin/env python3
"""
Test script to verify response processing logic.
"""

# Sample response from debug output - with initial greeting
sample_response_1 = """To access latest log: tail -F /tmp/agents_log/agent.latest.log
Running agent htcondor_mcp_client_agent, type exit to exit.
[user]: [htcondor_mcp_client_agent]: Hello! I'm your HTCondor assistant. How can I help you today?
[user]: [htcondor_mcp_client_agent]: Here are the first 10 jobs:

| ClusterId | ProcId | Status | Owner |
|-----------|--------|--------|-------|
| 6562147   | 0      | Held   | coenglan |
| 6562148   | 0      | Held   | coenglan |
| 6562149   | 0      | Held   | coenglan |
| 6657640   | 96      | Held   | jareddb2 |
| 6681977   | 0      | Running | maclwong |
| 6681981   | 0      | Running | maclwong |
| 6683795   | 0      | Running | wleight |
| 6681987   | 0      | Running | maclwong |
| 6681995   | 0      | Running | maclwong |
| 6658971   | 18      | Held   | wcas |

There are a total of 440 jobs.

"""

# Sample response with session creation
sample_response_2 = """To access latest log: tail -F /tmp/agents_log/agent.latest.log
Running agent htcondor_mcp_client_agent, type exit to exit.
[user]: [htcondor_mcp_client_agent]: Hello! I'm your HTCondor assistant. How can I help you today?
[user]: [htcondor_mcp_client_agent]: I'll create a new session for you.
[user]: [htcondor_mcp_client_agent]: Session created successfully. Here are the first 10 jobs:

| ClusterId | ProcId | Status | Owner |
|-----------|--------|--------|-------|
| 6562147   | 0      | Held   | coenglan |
| 6562148   | 0      | Held   | coenglan |
| 6562149   | 0      | Held   | coenglan |
| 6657640   | 96      | Held   | jareddb2 |
| 6681977   | 0      | Running | maclwong |
| 6681981   | 0      | Running | maclwong |
| 6683795   | 0      | Running | wleight |
| 6681987   | 0      | Running | maclwong |
| 6681995   | 0      | Running | maclwong |
| 6658971   | 18      | Held   | wcas |

There are a total of 440 jobs.

"""

def test_response_processing():
    """Test the response processing logic."""
    
    print("🧪 Testing response processing logic...")
    
    test_cases = [
        ("Response with greeting", sample_response_1),
        ("Response with session creation", sample_response_2)
    ]
    
    for test_name, sample_response in test_cases:
        print(f"\n{'='*50}")
        print(f"🧪 Testing: {test_name}")
        print(f"{'='*50}")
        
        # Split into lines like the main script does
        response_lines = sample_response.split('\n')
        print(f"📊 Total lines: {len(response_lines)}")
        
        # Apply the same cleaning logic as the main script
        cleaned_lines = []
        for line in response_lines:
            # Skip log messages
            if any(skip in line.lower() for skip in [
                'log setup complete', 'to access latest log', 'running agent', 
                'type exit to exit', 'tail -f'
            ]):
                print(f"🚫 Skipped log line: {line}")
                continue
            
            # Clean up agent response format
            if '[htcondor_mcp_client_agent]:' in line:
                parts = line.split('[htcondor_mcp_client_agent]:')
                if len(parts) > 1:
                    cleaned_lines.append(parts[1].strip())
                    print(f"✅ Cleaned agent line: {parts[1].strip()}")
            elif line.strip() and not line.startswith('[user]:'):
                cleaned_lines.append(line)
                print(f"✅ Kept line: {line}")
            else:
                print(f"🚫 Skipped line: {line}")
        
        final_response = '\n'.join(cleaned_lines).strip()
        
        print(f"\n📄 Final cleaned response:")
        print(final_response)
        print(f"\n📊 Final response length: {len(final_response)} characters")
        
        # Test tool call extraction
        query = "list all the jobs"
        response_lower = final_response.lower()
        
        print(f"\n🔧 Tool call extraction test:")
        print(f"  Query: {query}")
        print(f"  Contains 'clusterid': {'clusterid' in response_lower}")
        print(f"  Contains 'procid': {'procid' in response_lower}")
        print(f"  Contains 'status': {'status' in response_lower}")
        print(f"  Contains 'owner': {'owner' in response_lower}")
        print(f"  Contains 'there are a total of': {'there are a total of' in response_lower}")
        print(f"  Contains greeting: {'hello' in response_lower or 'htcondor assistant' in response_lower}")
        print(f"  Contains session creation: {'session' in response_lower and 'created' in response_lower}")
        
        # Test the tool detection logic
        if any(pattern in response_lower for pattern in [
            "clusterid", "procid", "status", "owner", "jobs from", "total jobs"
        ]):
            print("✅ Tool detection: list_jobs should be detected")
        else:
            print("❌ Tool detection: list_jobs NOT detected")
        
        # Test response validation
        if "clusterid" not in response_lower or "procid" not in response_lower:
            print("❌ Response validation: Missing table data")
        else:
            print("✅ Response validation: Has table data")
        
        # Test if greeting/session creation interferes
        if "hello" in response_lower or "htcondor assistant" in response_lower:
            print("⚠️  Response contains greeting - might need special handling")
        if "session" in response_lower and "created" in response_lower:
            print("⚠️  Response contains session creation - might need special handling")

if __name__ == "__main__":
    test_response_processing() 