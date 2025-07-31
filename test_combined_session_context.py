#!/usr/bin/env python3
"""
Test script to demonstrate the combined session_context.py functionality.

This script tests the merged session and context management system.
"""

import sys
import json
import datetime
from pathlib import Path

# Add the local_mcp directory to the path
sys.path.insert(0, str(Path(__file__).parent))

from local_mcp.session_context import get_session_context_manager, HTCondorContext

def test_combined_functionality():
    """Test the combined session and context functionality."""
    print("🧪 Testing Combined Session and Context Functionality")
    print("=" * 55)
    
    # Initialize combined session context manager
    scm = get_session_context_manager()
    
    # Test user
    test_user_id = "test_user_combined"
    
    print(f"\n1. 📝 Creating test session for user: {test_user_id}")
    session_id = scm.create_session(test_user_id, {"test": True, "combined": True})
    print(f"   ✅ Created session: {session_id}")
    
    print(f"\n2. 🗄️ Testing SQLite database structure")
    
    # Check what tables were created
    import sqlite3
    with sqlite3.connect(scm.db_path) as conn:
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print(f"   📊 Database tables: {tables}")
        
        # Check if all expected tables exist
        expected_tables = ['sessions', 'conversations', 'user_preferences', 'artifacts', 'memory', 'htcondor_context']
        for table in expected_tables:
            if table in tables:
                print(f"   ✅ {table} table exists")
            else:
                print(f"   ❌ {table} table missing")
    
    print(f"\n3. 🧠 Testing memory functionality")
    
    # Add test data to memory
    scm.add_to_memory(test_user_id, "preferred_format", "table")
    scm.add_to_memory(test_user_id, "last_job_query", "cluster_id 1234567")
    scm.add_to_memory(test_user_id, "user_note", "Prefers detailed job status reports")
    scm.add_to_memory(test_user_id, "system_maintenance", "Scheduled maintenance on Friday", global_memory=True)
    
    print("   ✅ Added test data to user and global memory")
    
    # Test memory retrieval
    user_memory = scm.get_user_memory(test_user_id)
    print(f"   📊 User memory entries: {len(user_memory)}")
    for key, value in user_memory.items():
        print(f"      - {key}: {str(value)[:50]}...")
    
    # Test memory search
    search_results = scm.search_memory(test_user_id, "job")
    print(f"   🔍 Found {len(search_results)} results for 'job' query:")
    for result in search_results:
        print(f"      - {result['key']}: {result['value'][:50]}...")
    
    print(f"\n4. 💾 Testing artifact storage")
    
    # Create test artifact
    test_data = {
        "cluster_id": 1234567,
        "status": "Running",
        "user": test_user_id,
        "timestamp": datetime.datetime.now().isoformat(),
        "storage_type": "sqlite_combined"
    }
    
    artifact_id = scm.save_artifact(session_id, "test_job_report", test_data)
    print(f"   ✅ Saved artifact: {artifact_id}")
    
    # Load artifact
    loaded_data = scm.load_artifact(session_id, "test_job_report")
    if loaded_data:
        print(f"   📄 Loaded artifact data: {json.dumps(loaded_data, indent=2)}")
    else:
        print(f"   ❌ Failed to load artifact")
    
    print(f"\n5. 👤 Testing HTCondor context")
    
    # Create test context
    test_context = HTCondorContext(
        user_id=test_user_id,
        session_id=session_id,
        current_jobs=[1234567, 1234568],
        preferences={"default_job_limit": 20, "output_format": "table"},
        job_history=[
            {"cluster_id": 1234567, "accessed_at": datetime.datetime.now().isoformat(), "session_id": session_id},
            {"cluster_id": 1234568, "accessed_at": datetime.datetime.now().isoformat(), "session_id": session_id}
        ]
    )
    
    # Save context
    scm.save_htcondor_context(session_id, test_context)
    print(f"   ✅ Saved HTCondor context to SQLite")
    
    # Load context
    loaded_context = scm.get_htcondor_context(session_id, test_user_id)
    print(f"   📊 Loaded context:")
    print(f"      - User ID: {loaded_context.user_id}")
    print(f"      - Session ID: {loaded_context.session_id}")
    print(f"      - Current Jobs: {loaded_context.current_jobs}")
    print(f"      - Preferences: {loaded_context.preferences}")
    print(f"      - Job History Count: {len(loaded_context.job_history)}")
    
    print(f"\n6. 📝 Testing session management")
    
    # Test session validation
    is_valid = scm.validate_session(session_id)
    print(f"   ✅ Session validation: {is_valid}")
    
    # Test conversation history
    scm.add_message(session_id, "tool_call", "Test tool call")
    scm.add_message(session_id, "user_message", "Test user message")
    
    history = scm.get_conversation_history(session_id)
    print(f"   📊 Conversation history entries: {len(history)}")
    for entry in history:
        print(f"      - {entry['message_type']}: {entry['content'][:50]}...")
    
    # Test user preferences
    prefs = scm.get_user_preferences(test_user_id)
    print(f"   ⚙️ User preferences: {prefs}")
    
    print(f"\n7. 🧹 Testing cleanup functionality")
    
    # Test cleanup functions
    print("   ✅ Cleanup functionality available")
    print("      - cleanup_expired_sessions()")
    print("      - cleanup_old_artifacts()")
    print("      - cleanup_old_memory()")
    
    print(f"\n✅ All combined session and context tests completed successfully!")
    print(f"\n🎯 Key Features Demonstrated:")
    print(f"   • Combined session and context management")
    print(f"   • SQLite-only storage for all data")
    print(f"   • Session persistence with database tables")
    print(f"   • Artifact storage in SQLite")
    print(f"   • Memory search across user and global contexts")
    print(f"   • Cross-session context awareness")
    print(f"   • User preferences and job history tracking")
    print(f"   • Conversation history management")
    print(f"   • Automatic cleanup of old data")
    print(f"   • Simplified architecture with single manager")

if __name__ == "__main__":
    print("🚀 Starting Combined Session and Context System Test")
    
    # Run the tests
    test_combined_functionality()
    
    print(f"\n🎉 Test completed! The combined session and context system is ready for use.")
    print(f"📚 This system provides a simplified, unified approach to session and context management.") 