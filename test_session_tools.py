#!/usr/bin/env python3
"""
Test script to directly call session history tools.
"""

import sys
from pathlib import Path

# Add the local_mcp directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from local_mcp.server import get_session_history, get_session_summary

def test_session_tools():
    """Test the session history tools directly."""
    print("🧪 Testing Session History Tools")
    print("=" * 40)
    
    # Test session ID from the conversation
    session_id = "d07b6c99-ac10-4656-bb9b-24d64e35b2bc"
    
    print(f"Testing session: {session_id}")
    
    # Test get_session_history
    print(f"\n1. Testing get_session_history...")
    try:
        history_result = get_session_history(session_id)
        print(f"   Success: {history_result.get('success', False)}")
        print(f"   Message: {history_result.get('message', 'No message')}")
        print(f"   Total entries: {history_result.get('total_entries', 0)}")
        if history_result.get('success'):
            print(f"   ✅ get_session_history worked!")
        else:
            print(f"   ❌ get_session_history failed: {history_result}")
    except Exception as e:
        print(f"   ❌ Exception in get_session_history: {e}")
    
    # Test get_session_summary
    print(f"\n2. Testing get_session_summary...")
    try:
        summary_result = get_session_summary(session_id)
        print(f"   Success: {summary_result.get('success', False)}")
        print(f"   Message: {summary_result.get('message', 'No message')}")
        if summary_result.get('success'):
            summary = summary_result.get('summary', {})
            print(f"   Total interactions: {summary.get('total_interactions', 0)}")
            print(f"   Tools used: {summary.get('tools_used', {})}")
            print(f"   ✅ get_session_summary worked!")
        else:
            print(f"   ❌ get_session_summary failed: {summary_result}")
    except Exception as e:
        print(f"   ❌ Exception in get_session_summary: {e}")

if __name__ == "__main__":
    test_session_tools() 