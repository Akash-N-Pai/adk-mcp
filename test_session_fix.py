#!/usr/bin/env python3
"""
Test script to verify the session history fix.
"""

import sys
from pathlib import Path

# Add the local_mcp directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from local_mcp.session_context import get_session_context_manager

def test_session_history_fix():
    """Test that session history functions now work correctly."""
    print("🧪 Testing Session History Fix")
    print("=" * 35)
    
    # Get the session context manager
    scm = get_session_context_manager()
    
    # Test session ID from the conversation
    session_id = "a7bea9bb-f56f-4753-aaea-eeba66e26712"
    
    print(f"Testing session: {session_id}")
    
    # Test get_session_history function
    print(f"\n1. Testing get_session_history...")
    try:
        # Import the function from server.py
        import sys
        sys.path.append('local_mcp')
        from server import get_session_history
        
        result = get_session_history(session_id)
        print(f"   Success: {result.get('success', False)}")
        if result.get('success'):
            print(f"   Total entries: {result.get('total_entries', 0)}")
            print(f"   Session info: {result.get('session_info', {}).get('user_id', 'unknown')}")
        else:
            print(f"   Error: {result.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test get_session_summary function
    print(f"\n2. Testing get_session_summary...")
    try:
        from server import get_session_summary
        
        result = get_session_summary(session_id)
        print(f"   Success: {result.get('success', False)}")
        if result.get('success'):
            summary = result.get('summary', {})
            print(f"   Total interactions: {summary.get('total_interactions', 0)}")
            print(f"   Tools used: {summary.get('tools_used', {})}")
            print(f"   Jobs referenced: {summary.get('jobs_referenced', [])}")
        else:
            print(f"   Error: {result.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    # Test get_user_conversation_memory function
    print(f"\n3. Testing get_user_conversation_memory...")
    try:
        from server import get_user_conversation_memory
        
        result = get_user_conversation_memory()
        print(f"   Success: {result.get('success', False)}")
        if result.get('success'):
            print(f"   Total sessions: {result.get('total_sessions', 0)}")
            print(f"   Total conversations: {result.get('total_conversations', 0)}")
            print(f"   Job references: {result.get('job_references', [])}")
        else:
            print(f"   Error: {result.get('message', 'Unknown error')}")
    except Exception as e:
        print(f"   Exception: {e}")
    
    print(f"\n✅ Session history fix test completed!")

if __name__ == "__main__":
    test_session_history_fix() 