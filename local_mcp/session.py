"""
Simplified Session Management for HTCondor MCP Agent

Provides persistent memory and multi-user session support with minimal complexity.
"""

import sqlite3
import json
import uuid
import datetime
import re
from pathlib import Path
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)

class SessionManager:
    """Simple session manager with database storage."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize with SQLite database."""
        if db_path is None:
            db_path = Path(__file__).parent / "sessions.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_timeout_hours = 200
        self._init_database()
    
    def _init_database(self):
        """Create database tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
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
            
            # Create indexes
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            conn.commit()
    
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