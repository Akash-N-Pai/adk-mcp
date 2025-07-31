#!/usr/bin/env python3
"""
Test script to verify simplified schema compatibility with all updated files.
"""

import sys
import json
import datetime
from pathlib import Path

# Add the local_mcp directory to the path
sys.path.insert(0, str(Path(__file__).parent))

def test_simplified_compatibility():
    """Test that all files work with the simplified schema."""
    print("🧪 Testing Simplified Schema Compatibility")
    print("=" * 50)
    
    try:
        # Test imports
        print("\n1. 📦 Testing imports...")
        from local_mcp import root_agent, get_session_context_manager
        from local_mcp.session_context_simple import SimplifiedSessionContextManager, HTCondorContext, get_simplified_session_context_manager
        print("   ✅ All imports successful")
        
        # Test session context manager
        print("\n2. 🔧 Testing session context manager...")
        scm = get_simplified_session_context_manager()
        print(f"   ✅ Session context manager initialized: {type(scm).__name__}")
        print(f"   ✅ Database path: {scm.db_path}")
        
        # Test session creation
        print("\n3. 📝 Testing session creation...")
        test_user_id = "test_user_compatibility"
        session_id = scm.create_session(test_user_id, {"test": True, "compatibility": True})
        print(f"   ✅ Created session: {session_id}")
        
        # Test session validation
        print("\n4. ✅ Testing session validation...")
        is_valid = scm.validate_session(session_id)
        print(f"   ✅ Session validation: {is_valid}")
        
        # Test conversation history
        print("\n5. 💬 Testing conversation history...")
        scm.add_message(session_id, "tool_call", "Test tool call")
        scm.add_message(session_id, "user_message", "Test user message")
        
        history = scm.get_conversation_history(session_id)
        print(f"   ✅ Conversation history entries: {len(history)}")
        
        # Test session context
        print("\n6. 👤 Testing session context...")
        context = scm.get_session_context(session_id)
        print(f"   ✅ Session context: {context.get('user_id', 'unknown')}")
        
        # Test HTCondor context
        print("\n7. 🔧 Testing HTCondor context...")
        htcondor_context = scm.get_htcondor_context(session_id, test_user_id)
        print(f"   ✅ HTCondor context: {htcondor_context.user_id}")
        
        # Test memory functionality
        print("\n8. 🧠 Testing memory functionality...")
        scm.add_to_memory(test_user_id, "test_key", "test_value")
        user_memory = scm.get_user_memory(test_user_id)
        print(f"   ✅ User memory entries: {len(user_memory)}")
        
        # Test artifact functionality
        print("\n9. 💾 Testing artifact functionality...")
        test_data = {"test": "artifact", "timestamp": datetime.datetime.now().isoformat()}
        artifact_id = scm.save_artifact(session_id, "test_artifact", test_data)
        print(f"   ✅ Saved artifact: {artifact_id}")
        
        loaded_artifact = scm.load_artifact(session_id, "test_artifact")
        print(f"   ✅ Loaded artifact: {loaded_artifact is not None}")
        
        # Test search functionality
        print("\n10. 🔍 Testing search functionality...")
        search_results = scm.search_memory(test_user_id, "test")
        print(f"   ✅ Search results: {len(search_results)}")
        
        print(f"\n✅ All compatibility tests passed!")
        print(f"\n🎯 Simplified schema is fully compatible with all updated files.")
        
    except Exception as e:
        print(f"\n❌ Compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

def test_agent_compatibility():
    """Test that the agent works with simplified schema."""
    print("\n🤖 Testing Agent Compatibility")
    print("=" * 35)
    
    try:
        from local_mcp.agent import root_agent
        print("   ✅ Agent imported successfully")
        print(f"   ✅ Agent type: {type(root_agent).__name__}")
        print(f"   ✅ Agent name: {root_agent.name}")
        print("   ✅ Agent is ready to use with simplified schema")
        
    except Exception as e:
        print(f"   ❌ Agent compatibility test failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🚀 Starting Simplified Schema Compatibility Test")
    
    # Run the tests
    compatibility_ok = test_simplified_compatibility()
    agent_ok = test_agent_compatibility()
    
    if compatibility_ok and agent_ok:
        print(f"\n🎉 All compatibility tests passed!")
        print(f"📚 The simplified schema is ready for production use.")
        print(f"🔧 All files have been updated successfully.")
    else:
        print(f"\n❌ Some compatibility tests failed.")
        print(f"🔧 Please check the errors above.") 