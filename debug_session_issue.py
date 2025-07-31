#!/usr/bin/env python3
"""
Debug script to check session history issues in simplified schema.
"""

import sys
from pathlib import Path

# Add the local_mcp directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from local_mcp.session_context_simple import get_simplified_session_context_manager

def debug_session_issue():
    """Debug the session history issue."""
    print("🔍 Debugging Session History Issue")
    print("=" * 40)
    
    # Get the simplified session context manager
    scm = get_simplified_session_context_manager()
    
    # Test session ID from the conversation
    session_id = "d07b6c99-ac10-4656-bb9b-24d64e35b2bc"
    
    print(f"Testing session: {session_id}")
    
    # Check if session exists
    print(f"\n1. Checking if session exists...")
    is_valid = scm.validate_session(session_id)
    print(f"   Session valid: {is_valid}")
    
    # Get session context
    print(f"\n2. Getting session context...")
    try:
        context = scm.get_session_context(session_id)
        print(f"   Context: {context}")
    except Exception as e:
        print(f"   Error getting context: {e}")
    
    # Get conversation history
    print(f"\n3. Getting conversation history...")
    try:
        history = scm.get_conversation_history(session_id)
        print(f"   History entries: {len(history)}")
        for i, entry in enumerate(history):
            print(f"   Entry {i+1}: {entry}")
    except Exception as e:
        print(f"   Error getting history: {e}")
    
    # Check database directly
    print(f"\n4. Checking database directly...")
    try:
        import sqlite3
        with sqlite3.connect(scm.db_path) as conn:
            # Check sessions table
            cursor = conn.execute("SELECT * FROM sessions WHERE session_id = ?", (session_id,))
            session_row = cursor.fetchone()
            print(f"   Session in database: {session_row is not None}")
            if session_row:
                print(f"   Session data: {session_row}")
            
            # Check conversations table
            cursor = conn.execute("SELECT * FROM conversations WHERE session_id = ?", (session_id,))
            conversations = cursor.fetchall()
            print(f"   Conversations in database: {len(conversations)}")
            for i, conv in enumerate(conversations):
                print(f"   Conversation {i+1}: {conv}")
                
    except Exception as e:
        print(f"   Error checking database: {e}")
    
    # Test adding a message
    print(f"\n5. Testing adding a message...")
    try:
        message_id = scm.add_message(session_id, "debug_test", "This is a debug test message")
        print(f"   Added message with ID: {message_id}")
        
        # Check if message was added
        history = scm.get_conversation_history(session_id)
        print(f"   History after adding message: {len(history)} entries")
        
    except Exception as e:
        print(f"   Error adding message: {e}")

if __name__ == "__main__":
    debug_session_issue() 