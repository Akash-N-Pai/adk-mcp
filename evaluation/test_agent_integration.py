#!/usr/bin/env python3
"""
Test script to verify agent integration for ADK evaluation.
This script helps debug agent communication issues.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))


async def test_agent_availability():
    """Test if the agent is available and can be imported."""
    print("🔍 Testing Agent Availability...")
    
    try:
        from local_mcp.agent import root_agent
        print("✅ Agent imported successfully")
        print(f"   Agent type: {type(root_agent)}")
        print(f"   Agent name: {getattr(root_agent, 'name', 'Unknown')}")
        return root_agent
    except ImportError as e:
        print(f"❌ Agent import failed: {e}")
        print("   Make sure google-adk is installed and GOOGLE_API_KEY is set")
        return None
    except Exception as e:
        print(f"❌ Unexpected error importing agent: {e}")
        return None


async def test_agent_methods(agent):
    """Test what methods are available on the agent."""
    print("\n🔍 Testing Agent Methods...")
    
    if not agent:
        print("❌ No agent available for method testing")
        return
    
    # Get all public methods
    methods = [m for m in dir(agent) if not m.startswith('_')]
    print(f"✅ Available methods: {methods}")
    
    # Check for common ADK methods
    common_methods = ['run', 'chat', 'generate', 'process_query', 'query']
    available_methods = [m for m in common_methods if hasattr(agent, m)]
    
    if available_methods:
        print(f"✅ Found common ADK methods: {available_methods}")
    else:
        print("⚠️  No common ADK methods found")
        print("   You may need to use subprocess communication")


async def test_agent_communication(agent):
    """Test actual communication with the agent."""
    print("\n🔍 Testing Agent Communication...")
    
    if not agent:
        print("❌ No agent available for communication testing")
        return
    
    test_query = "Show me all jobs"
    print(f"   Test query: '{test_query}'")
    
    # Try different communication methods
    methods_to_try = ['run', 'chat', 'generate', 'process_query', 'query']
    
    for method_name in methods_to_try:
        if hasattr(agent, method_name):
            method = getattr(agent, method_name)
            if callable(method):
                try:
                    print(f"   Trying {method_name}()...")
                    if asyncio.iscoroutinefunction(method):
                        response = await method(test_query)
                    else:
                        response = method(test_query)
                    
                    print(f"   ✅ {method_name}() succeeded!")
                    print(f"   Response type: {type(response)}")
                    print(f"   Response preview: {str(response)[:100]}...")
                    return method_name, response
                    
                except Exception as e:
                    print(f"   ❌ {method_name}() failed: {e}")
    
    print("❌ No communication methods worked")
    return None, None


async def test_evaluation_integration():
    """Test the evaluation framework integration."""
    print("\n🔍 Testing Evaluation Integration...")
    
    try:
        from evaluation.adk_evaluation import ADKEvaluator
        
        evaluator = ADKEvaluator()
        print("✅ ADKEvaluator created successfully")
        
        # Test a single case
        test_query = "Show me all jobs"
        print(f"   Testing query: '{test_query}'")
        
        response = await evaluator._interact_with_agent(test_query)
        print(f"   ✅ Agent interaction succeeded!")
        print(f"   Response: {response[:100]}...")
        
        # Test tool usage extraction
        tool_usage = evaluator._extract_tool_usage(response)
        print(f"   Tool usage detected: {tool_usage}")
        
        return True
        
    except Exception as e:
        print(f"❌ Evaluation integration failed: {e}")
        return False


async def test_htcondor_environment():
    """Test if HTCondor environment is available."""
    print("\n🔍 Testing HTCondor Environment...")
    
    try:
        import htcondor
        print("✅ HTCondor Python bindings available")
        
        # Try to connect to HTCondor
        try:
            schedd = htcondor.Schedd()
            print("✅ HTCondor Schedd connection successful")
            
            # Try a simple query
            ads = schedd.query("True", limit=1)
            print(f"✅ HTCondor query successful, found {len(ads)} jobs")
            
        except Exception as e:
            print(f"⚠️  HTCondor connection failed: {e}")
            print("   This is normal if not running on Atlas AF")
            
    except ImportError:
        print("❌ HTCondor Python bindings not available")
        print("   Install with: pip install htcondor")


def main():
    """Run all tests."""
    print("🧪 ADK Agent Integration Test Suite")
    print("=" * 50)
    
    # Test agent availability
    agent = asyncio.run(test_agent_availability())
    
    # Test agent methods
    asyncio.run(test_agent_methods(agent))
    
    # Test agent communication
    if agent:
        method_name, response = asyncio.run(test_agent_communication(agent))
    else:
        method_name, response = None, None
    
    # Test evaluation integration
    eval_success = asyncio.run(test_evaluation_integration())
    
    # Test HTCondor environment
    asyncio.run(test_htcondor_environment())
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    if agent:
        print("✅ Agent: Available")
    else:
        print("❌ Agent: Not available")
    
    if method_name:
        print(f"✅ Communication: {method_name}() method works")
    else:
        print("❌ Communication: No working method found")
    
    if eval_success:
        print("✅ Evaluation: Integration successful")
    else:
        print("❌ Evaluation: Integration failed")
    
    print("\n🎯 NEXT STEPS:")
    if agent and method_name:
        print("   ✅ Your agent is ready for evaluation!")
        print("   Run: python3 evaluation/adk_evaluation.py --verbose")
    else:
        print("   🔧 Fix agent integration issues first")
        print("   Check: evaluation/AGENT_INTEGRATION_GUIDE.md")
    
    print("\n📚 For detailed integration help, see:")
    print("   evaluation/AGENT_INTEGRATION_GUIDE.md")


if __name__ == "__main__":
    main() 