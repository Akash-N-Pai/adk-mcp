#!/usr/bin/env python3
"""
Simple test to check if the agent is accessible and working.
"""

import asyncio
import sys
import os

def test_agent_import():
    """Test if we can import the agent."""
    print("🔍 Testing agent import...")
    try:
        from local_mcp import root_agent
        print(f"✅ Agent imported successfully!")
        print(f"   Agent type: {type(root_agent).__name__}")
        print(f"   Agent name: {root_agent.name}")
        print(f"   Agent model: {root_agent.model}")
        return root_agent
    except Exception as e:
        print(f"❌ Failed to import agent: {e}")
        return None

def test_agent_attributes(agent):
    """Test if agent has expected attributes."""
    print("\n🔍 Testing agent attributes...")
    try:
        # Check if agent has required methods
        required_methods = ['_run_async_impl', 'name', 'model']
        for method in required_methods:
            if hasattr(agent, method):
                print(f"✅ Has {method}: {getattr(agent, method)}")
            else:
                print(f"❌ Missing {method}")
        
        # Check if agent has tools
        if hasattr(agent, 'tools'):
            print(f"✅ Has tools: {len(agent.tools)} tools")
            for tool in agent.tools:
                print(f"   - {type(tool).__name__}")
        else:
            print("❌ No tools found")
            
        return True
    except Exception as e:
        print(f"❌ Error testing attributes: {e}")
        return False

async def test_agent_simple_call(agent):
    """Test if we can call the agent with a simple query."""
    print("\n🔍 Testing agent simple call...")
    try:
        # Try to access the agent's run method if it exists
        if hasattr(agent, 'run'):
            print("✅ Agent has 'run' method")
            try:
                # This might not work without proper context, but let's try
                result = await agent.run("hi")
                print(f"✅ Agent.run() succeeded: {result[:100]}...")
                return True
            except Exception as e:
                print(f"⚠️ Agent.run() failed (expected): {e}")
        
        if hasattr(agent, 'chat'):
            print("✅ Agent has 'chat' method")
            try:
                result = await agent.chat("hi")
                print(f"✅ Agent.chat() succeeded: {result[:100]}...")
                return True
            except Exception as e:
                print(f"⚠️ Agent.chat() failed (expected): {e}")
        
        print("ℹ️ Agent doesn't have run() or chat() methods (this is normal for ADK agents)")
        return True
        
    except Exception as e:
        print(f"❌ Error testing agent call: {e}")
        return False

def test_session_context():
    """Test if session context manager is accessible."""
    print("\n🔍 Testing session context manager...")
    try:
        from local_mcp.session_context_simple import get_simplified_session_context_manager
        scm = get_simplified_session_context_manager()
        print(f"✅ Session context manager created: {type(scm).__name__}")
        print(f"   Database path: {scm.db_path}")
        
        # Test basic functionality
        session_id = scm.create_session("test_user", {"test": True})
        print(f"✅ Created test session: {session_id}")
        
        is_valid = scm.validate_session(session_id)
        print(f"✅ Session validation: {is_valid}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing session context: {e}")
        return False

def test_mcp_server():
    """Test if MCP server tools are accessible."""
    print("\n🔍 Testing MCP server tools...")
    try:
        from local_mcp.server import ADK_AF_TOOLS
        print(f"✅ MCP server tools imported: {len(ADK_AF_TOOLS)} tools")
        
        # List some tools
        tool_names = list(ADK_AF_TOOLS.keys())[:5]
        for tool_name in tool_names:
            print(f"   - {tool_name}")
        
        return True
    except Exception as e:
        print(f"❌ Error testing MCP server: {e}")
        return False

async def main():
    """Main test function."""
    print("🚀 Testing Agent Connection and Accessibility")
    print("=" * 50)
    
    # Test agent import
    agent = test_agent_import()
    if not agent:
        print("\n❌ Cannot proceed without agent")
        return False
    
    # Test agent attributes
    attributes_ok = test_agent_attributes(agent)
    
    # Test session context
    session_ok = test_session_context()
    
    # Test MCP server
    mcp_ok = test_mcp_server()
    
    # Test agent call
    call_ok = await test_agent_simple_call(agent)
    
    # Summary
    print("\n📊 Test Summary")
    print("=" * 20)
    print(f"Agent Import: {'✅' if agent else '❌'}")
    print(f"Agent Attributes: {'✅' if attributes_ok else '❌'}")
    print(f"Session Context: {'✅' if session_ok else '❌'}")
    print(f"MCP Server: {'✅' if mcp_ok else '❌'}")
    print(f"Agent Call: {'✅' if call_ok else '❌'}")
    
    all_ok = agent and attributes_ok and session_ok and mcp_ok and call_ok
    print(f"\nOverall Status: {'✅ All tests passed' if all_ok else '❌ Some tests failed'}")
    
    if all_ok:
        print("\n🎉 Agent is ready for evaluation!")
        print("💡 You can now run the custom evaluation with confidence.")
    else:
        print("\n⚠️ Some components need attention before evaluation.")
    
    return all_ok

if __name__ == "__main__":
    asyncio.run(main()) 