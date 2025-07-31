"""
Simplified Session and Context Management for HTCondor MCP System

This module provides both basic session management and ADK Context functionality
using a simplified SQLite schema with only 3 tables.
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

class SimplifiedSessionContextManager:
    """Simplified session and context manager using only 3 tables."""
    
    def __init__(self, db_path: Optional[str] = None):
        """Initialize with SQLite database."""
        if db_path is None:
            db_path = Path(__file__).parent / "sessions_simple.db"
        
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.session_timeout_hours = 200
        self._init_database()
    
    def _init_database(self):
        """Create simplified database tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Core sessions table with metadata
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
            
            # Unified conversations table for all data
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
            
            # Create indexes for better performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_session_id ON conversations(session_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_conversations_type ON conversations(message_type)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_user_id ON sessions(user_id)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_active ON sessions(is_active)")
            
            conn.commit()
    
    # ===== SESSION MANAGEMENT METHODS =====
    
    def create_session(self, user_id: str, metadata: Optional[Dict] = None) -> str:
        """Create a new session."""
        session_id = str(uuid.uuid4())
        
        # Merge with default preferences
        default_prefs = {
            "default_job_limit": 10,
            "output_format": "table",
            "auto_refresh_interval": 30
        }
        
        if metadata is None:
            metadata = {}
        
        # Add default preferences if not present
        if "preferences" not in metadata:
            metadata["preferences"] = default_prefs
        
        metadata_json = json.dumps(metadata)
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO sessions (session_id, user_id, metadata)
                VALUES (?, ?, ?)
            """, (session_id, user_id, metadata_json))
            conn.commit()
        
        logger.info(f"Created session {session_id} for user {user_id}")
        return session_id
    
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
    
    def get_session_metadata(self, session_id: str) -> Dict:
        """Get session metadata."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT metadata FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if row:
                return json.loads(row[0])
            return {}
    
    def update_session_metadata(self, session_id: str, metadata: Dict):
        """Update session metadata."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE sessions SET metadata = ? WHERE session_id = ?
            """, (json.dumps(metadata), session_id))
            conn.commit()
    
    def get_session_context(self, session_id: str) -> Dict:
        """Get session context including history and preferences."""
        if not self.validate_session(session_id):
            return {"error": "Invalid or expired session"}
        
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("SELECT user_id, metadata FROM sessions WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()
            
            if not row:
                return {"error": "Session not found"}
            
            user_id = row['user_id']
            metadata = json.loads(row['metadata'])
            history = self.get_conversation_history(session_id, limit=10)
            
            return {
                "user_id": user_id,
                "preferences": metadata.get('preferences', {}),
                "recent_history": history,
                "job_references": self._extract_job_references(history)
            }
    
    def _extract_job_references(self, history: List[Dict]) -> List[str]:
        """Extract job cluster IDs from conversation history."""
        job_ids = []
        for msg in history:
            if msg['message_type'] == 'tool_call':
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
            metadata = self.get_session_metadata(session_id)
            
            # Extract context from metadata
            current_jobs = metadata.get('current_jobs', [])
            preferences = metadata.get('preferences', {})
            last_query = metadata.get('last_query')
            job_history = metadata.get('job_history', [])
            
            return HTCondorContext(
                user_id=user_id,
                session_id=session_id,
                current_jobs=current_jobs,
                preferences=preferences,
                last_query=last_query,
                job_history=job_history
            )
                    
        except Exception as e:
            logger.error(f"Failed to get HTCondor context: {e}")
            # Return basic context on error
            return HTCondorContext(user_id=user_id, session_id=session_id)
    
    def save_htcondor_context(self, session_id: str, context: HTCondorContext):
        """Save HTCondor context to session metadata."""
        try:
            metadata = self.get_session_metadata(session_id)
            
            # Update metadata with context data
            metadata.update({
                'current_jobs': context.current_jobs,
                'preferences': context.preferences,
                'last_query': context.last_query,
                'job_history': context.job_history,
                'updated_at': datetime.datetime.now().isoformat()
            })
            
            self.update_session_metadata(session_id, metadata)
                
        except Exception as e:
            logger.error(f"Failed to save HTCondor context: {e}")
    
    def save_artifact(self, session_id: str, name: str, data: Any) -> str:
        """Save an artifact as a conversation entry."""
        try:
            artifact_data = {
                "artifact_id": f"{session_id}_{name}_{uuid.uuid4().hex[:8]}",
                "name": name,
                "data": data,
                "created_at": datetime.datetime.now().isoformat()
            }
            
            conversation_id = self.add_message(
                session_id, 
                "artifact", 
                json.dumps(artifact_data, default=str)
            )
            
            logger.info(f"Saved artifact {artifact_data['artifact_id']} for session {session_id}")
            return artifact_data['artifact_id']
            
        except Exception as e:
            logger.error(f"Failed to save artifact: {e}")
            raise
    
    def load_artifact(self, session_id: str, name: str) -> Optional[Dict]:
        """Load an artifact from conversation history."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT content 
                    FROM conversations 
                    WHERE session_id = ? AND message_type = 'artifact' AND content LIKE ?
                    ORDER BY timestamp DESC 
                    LIMIT 1
                """, (session_id, f'%"name": "{name}"%'))
                row = cursor.fetchone()
                
                if row:
                    artifact_data = json.loads(row[0])
                    return {
                        "id": artifact_data["artifact_id"],
                        "name": artifact_data["name"],
                        "session_id": session_id,
                        "created_at": artifact_data["created_at"],
                        "data": artifact_data["data"]
                    }
                return None
                
        except Exception as e:
            logger.error(f"Failed to load artifact: {e}")
            return None
    
    def search_memory(self, user_id: str, query: str) -> List[Dict]:
        """Search memory in conversation history."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT c.content, c.message_type, s.user_id
                    FROM conversations c
                    JOIN sessions s ON c.session_id = s.session_id
                    WHERE (s.user_id = ? OR c.message_type = 'global_memory')
                    AND (c.content LIKE ? OR c.content LIKE ?)
                    ORDER BY c.timestamp DESC
                """, (user_id, f"%{query}%", f"%{query}%"))
                
                results = []
                for row in cursor.fetchall():
                    try:
                        content_data = json.loads(row[0])
                        results.append({
                            "source": f"{row[1]}_memory",
                            "key": content_data.get("key", "unknown"),
                            "value": content_data.get("value", ""),
                            "relevance": "high" if row[2] == user_id else "medium"
                        })
                    except:
                        continue
                
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
        """Add information to memory as conversation entry."""
        try:
            memory_type = "global_memory" if global_memory else "user_memory"
            memory_data = {
                "memory_id": f"{user_id}_{key}_{uuid.uuid4().hex[:8]}" if not global_memory else f"global_{key}_{uuid.uuid4().hex[:8]}",
                "user_id": user_id if not global_memory else None,
                "key": key,
                "value": str(value),
                "memory_type": memory_type,
                "updated_at": datetime.datetime.now().isoformat()
            }
            
            # Find a session to attach this memory to (or create a system session)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT session_id FROM sessions 
                    WHERE user_id = ? AND is_active = TRUE 
                    ORDER BY last_activity DESC LIMIT 1
                """, (user_id,))
                row = cursor.fetchone()
                
                if row:
                    session_id = row[0]
                else:
                    # Create a system session for memory storage
                    session_id = self.create_session(user_id, {"system_session": True})
            
            self.add_message(session_id, memory_type, json.dumps(memory_data))
                
        except Exception as e:
            logger.error(f"Failed to add to memory: {e}")
    
    def get_user_memory(self, user_id: str) -> Dict[str, Any]:
        """Get all memory for a user from conversation history."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT c.content FROM conversations c
                    JOIN sessions s ON c.session_id = s.session_id
                    WHERE s.user_id = ? AND c.message_type = 'user_memory'
                    ORDER BY c.timestamp DESC
                """, (user_id,))
                
                memory = {}
                for row in cursor.fetchall():
                    try:
                        memory_data = json.loads(row[0])
                        memory[memory_data["key"]] = memory_data["value"]
                    except:
                        continue
                return memory
                
        except Exception as e:
            logger.error(f"Failed to get user memory: {e}")
            return {}
    
    def get_global_memory(self) -> Dict[str, Any]:
        """Get global memory from conversation history."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute("""
                    SELECT content FROM conversations 
                    WHERE message_type = 'global_memory'
                    ORDER BY timestamp DESC
                """)
                
                memory = {}
                for row in cursor.fetchall():
                    try:
                        memory_data = json.loads(row[0])
                        memory[memory_data["key"]] = memory_data["value"]
                    except:
                        continue
                return memory
                
        except Exception as e:
            logger.error(f"Failed to get global memory: {e}")
            return {}
    
    def cleanup_old_data(self, days: int = 30):
        """Clean up old conversation data."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    DELETE FROM conversations 
                    WHERE timestamp < datetime('now', '-{} days')
                """.format(days))
                conn.commit()
                
            logger.info(f"Cleaned up conversations older than {days} days")
                    
        except Exception as e:
            logger.error(f"Failed to cleanup old data: {e}")

# Global simplified session context manager instance
_simplified_session_context_manager = None

def get_simplified_session_context_manager() -> SimplifiedSessionContextManager:
    """Get the global simplified session context manager instance."""
    global _simplified_session_context_manager
    if _simplified_session_context_manager is None:
        _simplified_session_context_manager = SimplifiedSessionContextManager()
    return _simplified_session_context_manager 