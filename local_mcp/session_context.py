"""
Combined Session and Context Management for HTCondor MCP System

This module provides both basic session management and ADK Context functionality
using SQLite storage for complete environment compatibility.
"""

import sqlite3
import json
import uuid
import datetime
import re
import os
import logging
from pathlib import Path
from typing import Optional, Dict, List, Any
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

@dataclass
class HTCondorContext:
    """HTCondor-specific context data."""
    user_id: str
    session_id: str
    current_jobs: List[int] = None
    preferences: Dict[str, Any] = None
    last_query: Optional[str] = None
    job_history: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.current_jobs is None:
            self.current_jobs = []
        if self.preferences is None:
            self.preferences = {}
        if self.job_history is None:
            self.job_history = []

class SessionContextManager:
    """Combined session and context manager using SQLite storage."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize with SQLite database."""
        if db_path is None:
            db_path = Path(__file__).parent / "sessions.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_timeout_hours = 200
        self._init_database()
    
    def _init_database(self):
        """Create all database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            # Basic session management tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    is_active BOOLEAN DEFAULT TRUE,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    conversation_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    message_type TEXT NOT NULL,
                    content TEXT NOT NULL,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS user_preferences (
                    user_id TEXT PRIMARY KEY,
                    preferences TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Context management tables
            conn.execute("""
                CREATE TABLE IF NOT EXISTS artifacts (
                    artifact_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    memory_id TEXT PRIMARY KEY,
                    user_id TEXT,
                    key TEXT NOT NULL,
                    value TEXT NOT NULL,
                    memory_type TEXT NOT NULL CHECK (memory_type IN ('user', 'global')),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS htcondor_context (
                    session_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    current_jobs TEXT DEFAULT '[]',
                    preferences TEXT DEFAULT '{}',
                    last_query TEXT,
                    job_history TEXT DEFAULT '[]',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (session_id)
                )
            """)
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_session_name ON artifacts(session_id, name)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_user_type ON memory(user_id, memory_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_memory_key ON memory(key)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_htcondor_context_user ON htcondor_context(user_id)")
            
            conn.commit()
    
    # ===== SESSION MANAGEMENT METHODS =====
    
    def create_session(self, user_id: str, metadata: Optional[Dict] = None) -> str:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        metadata_json = json.dumps(metadata or {})
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sessions (session_id, user_id, metadata)
                VALUES (?, ?, ?)
            """, (session_id, user_id, metadata_json))
            conn.commit()
        
        # Create default preferences
        self._ensure_user_preferences(user_id)
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id
    
    def _ensure_user_preferences(self, user_id: str):
        """Ensure user has default preferences."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT user_id FROM user_preferences WHERE user_id = ?", (user_id,))
            if not cursor.fetchone():
                default_prefs = {
                    "default_job_limit": 10,
                    "output_format": "table",
                    "auto_refresh_interval": 30
                }
                conn.execute("""
                    INSERT INTO user_preferences (user_id, preferences)
                    VALUES (?, ?)
                """, (user_id, json.dumps(default_prefs)))
                conn.commit()
    
    def validate_session(self, session_id: str) -> bool:
        """Check if session is valid and active."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT is_active, last_activity FROM sessions WHERE session_id = ?
            """, (session_id,))
            row = cursor.fetchone()
            
            if not row or not row[0]:
                return False
            
            # Check expiration
            last_activity = datetime.datetime.fromisoformat(row[1])
            if datetime.datetime.now() - last_activity > datetime.timedelta(hours=self.session_timeout_hours):
                self.deactivate_session(session_id)
                return False
            
            return True
    
    def update_session_activity(self, session_id: str):
        """Update session activity timestamp."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE sessions SET last_activity = CURRENT_TIMESTAMP WHERE session_id = ?
            """, (session_id,))
            conn.commit()
    
    def deactivate_session(self, session_id: str):
        """Deactivate a session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("UPDATE sessions SET is_active = FALSE WHERE session_id = ?", (session_id,))
            conn.commit()
    
    def add_message(self, session_id: str, message_type: str, content: str) -> str:
        """Add a message to conversation history."""
        if not self.validate_session(session_id):
            raise ValueError("Invalid or expired session")
        
        conversation_id = str(uuid.uuid4())
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO conversations (conversation_id, session_id, message_type, content)
                VALUES (?, ?, ?, ?)
            """, (conversation_id, session_id, message_type, content))
            conn.commit()
        
        self.update_session_activity(session_id)
        return conversation_id
    
    def get_conversation_history(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get conversation history for a session."""
        if not self.validate_session(session_id):
            return []
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT * FROM conversations 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
            """, (session_id, limit))
            
            conversations = [dict(row) for row in cursor.fetchall()]
            return list(reversed(conversations))  # Return in chronological order
    
    def get_user_preferences(self, user_id: str) -> Dict:
        """Get user preferences."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT preferences FROM user_preferences WHERE user_id = ?", (user_id,))
            row = cursor.fetchone()
            
            if row:
                return json.loads(row[0])
            return {}
    
    def update_user_preferences(self, user_id: str, preferences: Dict):
        """Update user preferences."""
        current_prefs = self.get_user_preferences(user_id)
        current_prefs.update(preferences)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO user_preferences (user_id, preferences)
                VALUES (?, ?)
            """, (user_id, json.dumps(current_prefs)))
            conn.commit()
    
    def get_session_context(self, session_id: str) -> Dict:
        """Get session context including history and preferences."""
        if not self.validate_session(session_id):
            return {"error": "Invalid or expired session"}
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT user_id FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if not row:
                return {"error": "Session not found"}
            
            user_id = row['user_id']
            history = self.get_conversation_history(session_id, limit=10)
            preferences = self.get_user_preferences(user_id)
            
            return {
                "user_id": user_id,
                "preferences": preferences,
                "recent_history": history,
                "job_references": self._extract_job_references(history)
            }
    
    def _extract_job_references(self, history: List[Dict]) -> List[str]:
        """Extract job cluster IDs from conversation history."""
        job_ids = []
        for msg in history:
            content = msg['content'].lower()
            # Look for 6+ digit numbers (likely job cluster IDs)
            numbers = re.findall(r'\b\d{6,}\b', content)
            job_ids.extend(numbers)
        return list(set(job_ids))  # Remove duplicates
    
    def cleanup_expired_sessions(self):
        """Clean up expired sessions."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE sessions 
                SET is_active = FALSE 
                WHERE last_activity < datetime('now', '-{} hours')
            """.format(self.session_timeout_hours))
            conn.commit()
        
        logger.info("Cleaned up expired sessions")
    
    # ===== CONTEXT MANAGEMENT METHODS =====
    
    def get_htcondor_context(self, session_id: str, user_id: str) -> HTCondorContext:
        """Get or create HTCondor-specific context for a session."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT current_jobs, preferences, last_query, job_history 
                    FROM htcondor_context 
                    WHERE session_id = ?
                """, (session_id,))
                row = cursor.fetchone()
                
                if row:
                    # Load existing context from database
                    current_jobs = json.loads(row[0]) if row[0] else []
                    preferences = json.loads(row[1]) if row[1] else {}
                    last_query = row[2]
                    job_history = json.loads(row[3]) if row[3] else []
                    
                    return HTCondorContext(
                        user_id=user_id,
                        session_id=session_id,
                        current_jobs=current_jobs,
                        preferences=preferences,
                        last_query=last_query,
                        job_history=job_history
                    )
                else:
                    # Create new context
                    preferences = self.get_user_preferences(user_id)
                    htcondor_context = HTCondorContext(
                        user_id=user_id,
                        session_id=session_id,
                        preferences=preferences
                    )
                    
                    # Save to database
                    self.save_htcondor_context(session_id, htcondor_context)
                    return htcondor_context
                    
        except Exception as e:
            logger.error(f"Failed to get HTCondor context: {e}")
            # Return basic context on error
            return HTCondorContext(user_id=user_id, session_id=session_id)
    
    def save_htcondor_context(self, session_id: str, context: HTCondorContext):
        """Save HTCondor context to SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO htcondor_context 
                    (session_id, user_id, current_jobs, preferences, last_query, job_history, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (
                    session_id,
                    context.user_id,
                    json.dumps(context.current_jobs),
                    json.dumps(context.preferences),
                    context.last_query,
                    json.dumps(context.job_history)
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to save HTCondor context: {e}")
    
    def save_artifact(self, session_id: str, name: str, data: Any) -> str:
        """Save an artifact to SQLite database."""
        try:
            artifact_id = f"{session_id}_{name}_{uuid.uuid4().hex[:8]}"
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO artifacts (artifact_id, session_id, name, data)
                    VALUES (?, ?, ?, ?)
                """, (artifact_id, session_id, name, json.dumps(data, default=str)))
                conn.commit()
            
            logger.info(f"Saved artifact {artifact_id} for session {session_id}")
            return artifact_id
            
        except Exception as e:
            logger.error(f"Failed to save artifact: {e}")
            raise
    
    def load_artifact(self, session_id: str, name: str) -> Optional[Dict]:
        """Load an artifact from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT artifact_id, data, created_at 
                    FROM artifacts 
                    WHERE session_id = ? AND name = ? 
                    ORDER BY created_at DESC 
                    LIMIT 1
                """, (session_id, name))
                row = cursor.fetchone()
                
                if row:
                    return {
                        "id": row[0],
                        "name": name,
                        "session_id": session_id,
                        "created_at": row[2],
                        "data": json.loads(row[1])
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to load artifact: {e}")
            return None
    
    def search_memory(self, user_id: str, query: str) -> List[Dict]:
        """Search memory in SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT key, value, memory_type 
                    FROM memory 
                    WHERE (user_id = ? OR memory_type = 'global') 
                    AND (key LIKE ? OR value LIKE ?)
                    ORDER BY updated_at DESC
                """, (user_id, f"%{query}%", f"%{query}%"))
                
                results = []
                for row in cursor.fetchall():
                    results.append({
                        "source": f"{row[2]}_memory",
                        "key": row[0],
                        "value": row[1],
                        "relevance": "high" if row[2] == "user" else "medium"
                    })
                
                return results
                
        except Exception as e:
            logger.error(f"Failed to search memory: {e}")
            return []
    
    def update_job_context(self, context: HTCondorContext, cluster_id: int):
        """Update context with job information."""
        if cluster_id not in context.current_jobs:
            context.current_jobs.append(cluster_id)
        
        # Add to job history
        job_entry = {
            "cluster_id": cluster_id,
            "accessed_at": datetime.datetime.now().isoformat(),
            "session_id": context.session_id
        }
        context.job_history.append(job_entry)
        
        # Keep only recent history
        if len(context.job_history) > 50:
            context.job_history = context.job_history[-50:]
        
        # Save updated context
        self.save_htcondor_context(context.session_id, context)
    
    def add_to_memory(self, user_id: str, key: str, value: Any, global_memory: bool = False):
        """Add information to memory in SQLite database."""
        try:
            memory_type = "global" if global_memory else "user"
            memory_id = f"{user_id}_{key}_{uuid.uuid4().hex[:8]}" if not global_memory else f"global_{key}_{uuid.uuid4().hex[:8]}"
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO memory (memory_id, user_id, key, value, memory_type, updated_at)
                    VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                """, (memory_id, user_id if not global_memory else None, key, str(value), memory_type))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to add to memory: {e}")
    
    def get_user_memory(self, user_id: str) -> Dict[str, Any]:
        """Get all memory for a user from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT key, value FROM memory 
                    WHERE user_id = ? AND memory_type = 'user'
                    ORDER BY updated_at DESC
                """, (user_id,))
                
                memory = {}
                for row in cursor.fetchall():
                    memory[row[0]] = row[1]
                return memory
                
        except Exception as e:
            logger.error(f"Failed to get user memory: {e}")
            return {}
    
    def get_global_memory(self) -> Dict[str, Any]:
        """Get global memory from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT key, value FROM memory 
                    WHERE memory_type = 'global'
                    ORDER BY updated_at DESC
                """)
                
                memory = {}
                for row in cursor.fetchall():
                    memory[row[0]] = row[1]
                return memory
                
        except Exception as e:
            logger.error(f"Failed to get global memory: {e}")
            return {}
    
    def cleanup_old_artifacts(self, days: int = 7):
        """Clean up old artifacts from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    DELETE FROM artifacts 
                    WHERE created_at < datetime('now', '-{} days')
                """.format(days))
                conn.commit()
                
            logger.info(f"Cleaned up artifacts older than {days} days")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup artifacts: {e}")
    
    def cleanup_old_memory(self, days: int = 30):
        """Clean up old memory entries from SQLite database."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    DELETE FROM memory 
                    WHERE updated_at < datetime('now', '-{} days')
                """.format(days))
                conn.commit()
                
            logger.info(f"Cleaned up memory older than {days} days")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup memory: {e}")

# Global session context manager instance
_session_context_manager = None

def get_session_context_manager() -> SessionContextManager:
    """Get the global session context manager instance."""
    global _session_context_manager
    if _session_context_manager is None:
        _session_context_manager = SessionContextManager()
    return _session_context_manager 