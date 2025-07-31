import asyncio
import json
import logging
import os
import datetime
import getpass
import sqlite3
from collections import defaultdict

import mcp.server.stdio
from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type
from mcp import types as mcp_types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import htcondor
from typing import Optional

# Import combined session context management - handle both relative and absolute imports
try:
    from .session_context import get_session_context_manager
except ImportError:
    # When running server.py directly, use absolute import
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from local_mcp.session_context import get_session_context_manager

load_dotenv()

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "mcp_server_activity.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE_PATH, mode="w")],
)

logging.info("Creating MCP Server instance for HTCondor...")
app = Server("htcondor-mcp-server")

# Initialize combined session context management
session_context_manager = get_session_context_manager()

def get_session_context(tool_context=None):
    """Extract session context from tool context."""
    if tool_context and isinstance(tool_context, dict):
        return tool_context.get('session_id'), tool_context.get('user_id')
    return None, None

def get_last_active_session(user_id=None):
    """Get the last active session for a user."""
    if user_id is None:
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    try:
        with sqlite3.connect(session_context_manager.db_path) as conn:
            cursor = conn.execute("""
                SELECT session_id, created_at, last_activity 
                FROM sessions 
                WHERE user_id = ? AND is_active = 1 
                ORDER BY last_activity DESC 
                LIMIT 1
            """, (user_id,))
            row = cursor.fetchone()
            return row if row else None
    except Exception as e:
        logging.error(f"Error getting last active session: {e}")
        return None

def get_all_user_sessions_summary(user_id=None):
    """Get a summary of all sessions for a user."""
    if user_id is None:
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    logging.info(f"Getting sessions for user: {user_id}")
    
    try:
        with sqlite3.connect(session_context_manager.db_path) as conn:
            cursor = conn.execute("""
                SELECT s.session_id, s.created_at, s.last_activity, COUNT(c.conversation_id) as conversation_count
                FROM sessions s 
                LEFT JOIN conversations c ON s.session_id = c.session_id 
                WHERE s.user_id = ? 
                GROUP BY s.session_id 
                ORDER BY s.last_activity DESC
            """, (user_id,))
            rows = cursor.fetchall()
            logging.info(f"Found {len(rows)} sessions for user {user_id}")
            result = [dict(zip(['session_id', 'created_at', 'last_activity', 'conversation_count'], row)) for row in rows]
            logging.info(f"Returning sessions: {result}")
            return result
    except Exception as e:
        logging.error(f"Error getting user sessions summary: {e}")
        return []

def ensure_session_exists(tool_context=None, continue_last_session=True):
    """Ensure a session exists, create one if it doesn't."""
    session_id, user_id = get_session_context(tool_context)
    
    if session_id is None:
        # Get current system username
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
        
        if continue_last_session:
            # Try to continue the last active session
            last_session = get_last_active_session(user_id)
            if last_session:
                session_id = last_session[0]
                logging.info(f"Continuing last active session {session_id} for user {user_id}")
                return session_id, user_id
        
        # Create a new session
        session_id = session_context_manager.create_session(user_id, {})
        logging.info(f"Created new session {session_id} for user {user_id}")
    
    return session_id, user_id

def log_tool_call(session_id, user_id, tool_name, arguments, result):
    """Log tool call to conversation history."""
    logging.info(f"log_tool_call: session_id={session_id}, user_id={user_id}, tool_name={tool_name}")
    if session_id and session_context_manager.validate_session(session_id):
        try:
            tool_call_data = {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result
            }
            session_context_manager.add_message(session_id, "tool_call", str(tool_call_data))
            logging.info(f"Successfully logged tool call for session {session_id}")
        except Exception as e:
            logging.error(f"Failed to log tool call: {e}")
    else:
        logging.warning(f"No valid session_id for tool call: {tool_name}")

def list_jobs(owner: Optional[str] = None, status: Optional[str] = None, limit: int = 10, tool_context=None) -> dict:
    # Get combined session context manager
    scm = get_session_context_manager()
    
    # Extract session info from tool_context if available
    session_id = None
    user_id = None
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Using proper ADK ToolContext
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
        
        # Use user preferences from context
        if not limit and htcondor_ctx.preferences:
            limit = htcondor_ctx.preferences.get('default_job_limit', 10)
    else:
        # Fallback to old method
        session_id, user_id = ensure_session_exists(tool_context)
        
        # Use user preferences for default limit if available
        if session_id and scm.validate_session(session_id):
            context = scm.get_session_context(session_id)
            if context and not isinstance(context, dict):
                user_prefs = context.get('preferences', {})
                if not limit:
                    limit = user_prefs.get('default_job_limit', 10)
    
    schedd = htcondor.Schedd()
    constraints = []
    if owner is not None:
        constraints.append(f'Owner == "{owner}"')
    if status is not None:
        status_map = {
            "running": 2, "idle": 1, "held": 5,
            "completed": 4, "removed": 3,
            "transferring_output": 6, "suspended": 7,
        }
        code = status_map.get(status.lower())
        if code is not None:
            constraints.append(f"JobStatus == {code}")
    constraint = " and ".join(constraints) if constraints else "True"

    # Only request JSON-safe fields
    attrs = ["ClusterId", "ProcId", "JobStatus", "Owner"]
    ads = schedd.query(constraint, projection=attrs)
    total_jobs = len(ads)
    
    # Only return first 10 jobs to prevent token limit errors
    ads = ads[:limit]

    status_code_map = {
        1: "Idle",
        2: "Running",
        3: "Removed",
        4: "Completed",
        5: "Held",
        6: "Transferring Output",
        7: "Suspended"
    }

    def serialize_ad(ad):
        result = {}
        for a in attrs:
            v = ad.get(a)
            # Evaluate ExprTree to primitive (avoids JSON errors)
            if hasattr(v, "eval"):
                try:
                    v = v.eval()
                except Exception:
                    v = None
            result[a] = v
        # Add human-readable status
        status_num = result.get("JobStatus")
        result["Status"] = status_code_map.get(status_num, "Unknown")
        return result

    result = {
        "success": True, 
        "jobs": [serialize_ad(ad) for ad in ads],
        "total_jobs": total_jobs
    }
    
    # Log the tool call
    log_tool_call(session_id, user_id, "list_jobs", {"owner": owner, "status": status, "limit": limit}, result)
    
    return result


def get_job_status(cluster_id: int, tool_context=None) -> dict:
    # Get combined session context manager
    scm = get_session_context_manager()
    
    # Extract session info from tool_context if available
    session_id = None
    user_id = None
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Using proper ADK ToolContext
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
        
        # Update job context with this cluster_id
        if hasattr(tool_context, 'update_job_context'):
            tool_context.update_job_context(cluster_id)
    else:
        # Fallback to old method
        session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        schedd = htcondor.Schedd()
        ads = schedd.query(f"ClusterId == {cluster_id}")
        if not ads:
            result = {"success": False, "message": "Job not found"}
            log_tool_call(session_id, user_id, "get_job_status", {"cluster_id": cluster_id}, result)
            return result
        
        ad = ads[0]
        job_info = {}
        
        # Extract only the most useful information from the raw HTCondor output
        useful_fields = {
            "ClusterId": "Cluster ID",
            "ProcId": "Process ID",
            "JobStatus": "Job Status",
            "Owner": "Owner",
            "Cmd": "Command",
            "Arguments": "Arguments",
            "Iwd": "Working Directory",
            "JobUniverse": "Job Universe",
            "QDate": "Queue Date",
            "JobStartDate": "Job Start Date",
            "JobCurrentStartDate": "Current Start Date",
            "RemoteHost": "Execution Host",
            "RemoteUserCpu": "CPU Time Used",
            "RemoteSysCpu": "System CPU Time",
            "MemoryUsage": "Memory Used",
            "DiskUsage": "Disk Used",
            "RequestCpus": "Requested CPUs",
            "RequestMemory": "Requested Memory",
            "RequestDisk": "Requested Disk",
            "JobPrio": "Job Priority",
            "NumJobStarts": "Number of Starts",
            "JobRunCount": "Run Count",
            "ExitStatus": "Exit Status",
            "WallClockCheckpoint": "Wall Clock Time",
            "In": "Input File",
            "Out": "Output File",
            "Err": "Error File",
            "UserLog": "Log File"
        }
        
        for field_name, display_name in useful_fields.items():
            v = ad.get(field_name)
            if hasattr(v, "eval"):
                try:
                    v = v.eval()
                except Exception:
                    v = None
            if v is not None:
                # Format special fields
                if field_name == "JobStatus":
                    status_map = {
                        1: "Idle", 2: "Running", 3: "Removed", 4: "Completed",
                        5: "Held", 6: "Transferring Output", 7: "Suspended"
                    }
                    v = f"{v} ({status_map.get(v, 'Unknown')})"
                elif field_name == "JobUniverse":
                    universe_map = {
                        1: "Standard", 2: "Pipes", 3: "Linda", 4: "PVM",
                        5: "Vanilla", 6: "Scheduler", 7: "MPI", 9: "Grid",
                        10: "Java", 11: "Parallel", 12: "Local", 13: "Docker"
                    }
                    v = f"{v} ({universe_map.get(v, 'Unknown')})"
                elif field_name in ["QDate", "JobStartDate", "JobCurrentStartDate"] and v:
                    # Convert Unix timestamp to readable format
                    try:
                        v = datetime.datetime.fromtimestamp(v).isoformat()
                    except (ValueError, TypeError):
                        pass
                elif field_name in ["RequestMemory", "MemoryUsage"] and v:
                    # Format memory with units
                    if v >= 1024:
                        v = f"{v} MB ({v//1024} GB)"
                    else:
                        v = f"{v} MB"
                elif field_name in ["RequestDisk", "DiskUsage"] and v:
                    # Format disk with units
                    if v >= 1024:
                        v = f"{v} MB ({v//1024} GB)"
                    else:
                        v = f"{v} MB"
                elif field_name == "Arguments" and not v:
                    v = "(none)"
                elif field_name in ["In", "Out", "Err"] and not v:
                    v = "(default)"
                elif field_name == "WallClockCheckpoint" and v:
                    # Convert seconds to hours:minutes:seconds
                    try:
                        hours = int(v // 3600)
                        minutes = int((v % 3600) // 60)
                        seconds = int(v % 60)
                        v = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    except (ValueError, TypeError):
                        pass
                
                job_info[display_name] = v
        
        result = {
            "success": True,
            "cluster_id": cluster_id,
            "job_status": job_info,
            "note": "Most useful job information extracted from HTCondor"
        }
        
        log_tool_call(session_id, user_id, "get_job_status", {"cluster_id": cluster_id}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error retrieving job status: {str(e)}"}
        log_tool_call(session_id, user_id, "get_job_status", {"cluster_id": cluster_id}, result)
        return result


def submit_job(submit_description: dict, tool_context=None) -> dict:
    session_id, user_id = ensure_session_exists(tool_context)
    
    schedd = htcondor.Schedd()
    submit = htcondor.Submit(submit_description)
    with schedd.transaction() as txn:
        cid = submit.queue(txn)
    
    result = {"success": True, "cluster_id": cid}
    log_tool_call(session_id, user_id, "submit_job", {"submit_description": submit_description}, result)
    return result


# ===== ADVANCED JOB INFORMATION =====

def get_job_history(cluster_id: int, limit: int = 50, tool_context=None) -> dict:
    """Get job execution history including state changes and events."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        schedd = htcondor.Schedd()
        ads = schedd.query(f"ClusterId == {cluster_id}")
        if not ads:
            result = {"success": False, "message": "Job not found"}
            log_tool_call(session_id, user_id, "get_job_history", {"cluster_id": cluster_id, "limit": limit}, result)
            return result
        
        ad = ads[0]
        job_info = {}
        for k, v in ad.items():
            if hasattr(v, "eval"):
                try:
                    v = v.eval()
                except Exception:
                    v = None
            job_info[k] = v
        
        # Get actual job timestamps and create realistic history
        q_date = job_info.get("QDate")  # Queue date (submission time)
        job_start_date = job_info.get("JobStartDate")  # When job started
        job_current_start_date = job_info.get("JobCurrentStartDate")  # Current start time
        completion_date = job_info.get("CompletionDate")  # When job completed
        
        history_events = []
        
        # Add submission event
        if q_date:
            history_events.append({
                "timestamp": datetime.datetime.fromtimestamp(q_date).isoformat(),
                "event": "Job submitted",
                "status": "Idle"
            })
        
        # Add start event
        if job_start_date or job_current_start_date:
            start_time = job_current_start_date or job_start_date
            history_events.append({
                "timestamp": datetime.datetime.fromtimestamp(start_time).isoformat(),
                "event": "Job started",
                "status": "Running"
            })
        
        # Add completion event if job is completed
        if job_info.get("JobStatus") == 4 and completion_date:  # Completed
            history_events.append({
                "timestamp": datetime.datetime.fromtimestamp(completion_date).isoformat(),
                "event": "Job completed",
                "status": "Completed"
            })
        
        # If no real timestamps, provide current status info
        if not history_events:
            history_events.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "event": "Current status",
                "status": job_info.get("JobStatus", "Unknown")
            })
        
        result = {
            "success": True,
            "cluster_id": cluster_id,
            "current_status": job_info.get("JobStatus"),
            "history_events": history_events[:limit],
            "total_events": len(history_events),
            "note": "History based on actual job timestamps from HTCondor"
        }
        
        log_tool_call(session_id, user_id, "get_job_history", {"cluster_id": cluster_id, "limit": limit}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error retrieving job history: {str(e)}"}
        log_tool_call(session_id, user_id, "get_job_history", {"cluster_id": cluster_id, "limit": limit}, result)
        return result





# ===== SIMPLE SESSION MANAGEMENT TOOLS =====

def create_session(user_id: str, metadata: Optional[dict] = None, tool_context=None) -> dict:
    """Create a new session for a user."""
    session_id, _ = get_session_context(tool_context)  # We don't need user_id here since we're creating a session
    
    try:
        session_id = session_manager.create_session(user_id, metadata)
        result = {
            "success": True,
            "session_id": session_id,
            "user_id": user_id,
            "message": f"Session created successfully for user {user_id}"
        }
        
        log_tool_call(session_id, user_id, "create_session", {"user_id": user_id, "metadata": metadata}, result)
        return result
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to create session: {str(e)}"
        }
        log_tool_call(session_id, user_id, "create_session", {"user_id": user_id, "metadata": metadata}, result)
        return result

def get_session_info(session_id: str, tool_context=None) -> dict:
    """Get information about a session."""
    _, user_id = get_session_context(tool_context)  # We don't need session_id here since it's a parameter
    
    try:
        if not session_manager.validate_session(session_id):
            return {
                "success": False,
                "message": "Invalid or expired session"
            }
        
        context = session_manager.get_session_context(session_id)
        result = {
            "success": True,
            "session_info": context
        }
        
        log_tool_call(session_id, user_id, "get_session_info", {"session_id": session_id}, result)
        return result
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to get session info: {str(e)}"
        }
        log_tool_call(session_id, user_id, "get_session_info", {"session_id": session_id}, result)
        return result

def end_session(session_id: str, tool_context=None) -> dict:
    """End a session."""
    _, user_id = get_session_context(tool_context)  # We don't need session_id here since it's a parameter
    
    try:
        if session_manager.validate_session(session_id):
            session_manager.deactivate_session(session_id)
            result = {
                "success": True,
                "message": "Session ended successfully"
            }
        else:
            result = {
                "success": False,
                "message": "Session not found or already inactive"
            }
        
        log_tool_call(session_id, user_id, "end_session", {"session_id": session_id}, result)
        return result
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to end session: {str(e)}"
        }
        log_tool_call(session_id, user_id, "end_session", {"session_id": session_id}, result)
        return result

def get_session_history(session_id: str, tool_context=None) -> dict:
    """Get conversation history for a specific session."""
    # Get user_id from session context, but use the provided session_id
    _, user_id = get_session_context(tool_context)
    if user_id is None:
        # Try to get user_id from the session itself
        session_info = session_manager.get_session_context(session_id)
        user_id = session_info.get('user_id', 'unknown') if isinstance(session_info, dict) else 'unknown'
    
    # If still no user_id, try to get current system user
    if user_id == 'unknown':
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    try:
        if not session_manager.validate_session(session_id):
            result = {
                "success": False,
                "message": "Invalid or expired session"
            }
            log_tool_call(session_id, user_id, "get_session_history", {"session_id": session_id}, result)
            return result
        
        # Get conversation history from database
        history = session_manager.get_conversation_history(session_id)
        
        # Parse and format the history
        formatted_history = []
        for entry in history:
            try:
                # Parse the tool call data
                tool_data = eval(entry['content']) if isinstance(entry['content'], str) else entry['content']
                
                formatted_entry = {
                    "timestamp": entry['timestamp'],
                    "tool_name": tool_data.get('tool_name', 'Unknown'),
                    "arguments": tool_data.get('arguments', {}),
                    "result_summary": str(tool_data.get('result', {}))[:200] + "..." if len(str(tool_data.get('result', {}))) > 200 else str(tool_data.get('result', {}))
                }
                formatted_history.append(formatted_entry)
            except Exception as e:
                # Skip malformed entries
                continue
        
        result = {
            "success": True,
            "session_id": session_id,
            "total_entries": len(formatted_history),
            "conversation_history": formatted_history,
            "session_info": session_manager.get_session_context(session_id)
        }
        
        log_tool_call(session_id, user_id, "get_session_history", {"session_id": session_id}, result)
        return result
        
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to get session history: {str(e)}"
        }
        log_tool_call(session_id, user_id, "get_session_history", {"session_id": session_id}, result)
        return result

def list_user_sessions(user_id: Optional[str] = None, tool_context=None) -> dict:
    """List all sessions for the current user."""
    if user_id is None:
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    logging.info(f"list_user_sessions called with user_id: {user_id}")
    
    try:
        logging.info(f"Calling get_all_user_sessions_summary for user: {user_id}")
        sessions = get_all_user_sessions_summary(user_id)
        logging.info(f"get_all_user_sessions_summary returned: {sessions}")
        
        result = {
            "success": True,
            "user_id": user_id,
            "total_sessions": len(sessions),
            "sessions": sessions
        }
        
        logging.info(f"list_user_sessions result: {result}")
        log_tool_call(None, user_id, "list_user_sessions", {"user_id": user_id}, result)
        return result
        
    except Exception as e:
        logging.error(f"Exception in list_user_sessions: {e}", exc_info=True)
        result = {
            "success": False,
            "message": f"Failed to list user sessions: {str(e)}"
        }
        log_tool_call(None, user_id, "list_user_sessions", {"user_id": user_id}, result)
        return result

def continue_last_session(user_id: Optional[str] = None, tool_context=None) -> dict:
    """Continue the last active session for the user."""
    if user_id is None:
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    try:
        last_session = get_last_active_session(user_id)
        
        if last_session:
            session_id = last_session[0]
            session_info = session_manager.get_session_context(session_id)
            
            result = {
                "success": True,
                "message": f"Continuing session {session_id}",
                "session_id": session_id,
                "session_info": session_info
            }
        else:
            result = {
                "success": False,
                "message": "No active sessions found for user"
            }
        
        log_tool_call(last_session[0] if last_session else None, user_id, "continue_last_session", {"user_id": user_id}, result)
        return result
        
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to continue last session: {str(e)}"
        }
        log_tool_call(None, user_id, "continue_last_session", {"user_id": user_id}, result)
        return result

def get_user_conversation_memory(user_id: Optional[str] = None, limit: int = 50, tool_context=None) -> dict:
    """Get conversation memory across all sessions for a user."""
    if user_id is None:
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    try:
        # Get all sessions for the user
        sessions = get_all_user_sessions_summary(user_id)
        
        # Get conversation history from all sessions
        all_conversations = []
        for session in sessions:
            session_id = session['session_id']
            history = session_manager.get_conversation_history(session_id, limit=limit)
            
            for entry in history:
                try:
                    tool_data = eval(entry['content']) if isinstance(entry['content'], str) else entry['content']
                    
                    conversation_entry = {
                        "session_id": session_id,
                        "timestamp": entry['timestamp'],
                        "tool_name": tool_data.get('tool_name', 'Unknown'),
                        "arguments": tool_data.get('arguments', {}),
                        "result_summary": str(tool_data.get('result', {}))[:200] + "..." if len(str(tool_data.get('result', {}))) > 200 else str(tool_data.get('result', {}))
                    }
                    all_conversations.append(conversation_entry)
                except Exception:
                    continue
        
        # Sort by timestamp
        all_conversations.sort(key=lambda x: x['timestamp'])
        
        # Extract key information
        job_references = set()
        tool_usage = {}
        
        for conv in all_conversations:
            # Count tool usage
            tool_name = conv['tool_name']
            tool_usage[tool_name] = tool_usage.get(tool_name, 0) + 1
            
            # Extract job references
            args = conv['arguments']
            if 'cluster_id' in args:
                job_references.add(args['cluster_id'])
        
        result = {
            "success": True,
            "user_id": user_id,
            "total_sessions": len(sessions),
            "total_conversations": len(all_conversations),
            "recent_conversations": all_conversations[-limit:],  # Most recent conversations
            "job_references": list(job_references),
            "tool_usage_summary": tool_usage,
            "sessions_summary": sessions
        }
        
        log_tool_call(None, user_id, "get_user_conversation_memory", {"user_id": user_id, "limit": limit}, result)
        return result
        
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to get user conversation memory: {str(e)}"
        }
        log_tool_call(None, user_id, "get_user_conversation_memory", {"user_id": user_id, "limit": limit}, result)
        return result

def get_session_summary(session_id: str, tool_context=None) -> dict:
    """Get a summary of what was done in a session."""
    # Get user_id from session context, but use the provided session_id
    _, user_id = get_session_context(tool_context)
    if user_id is None:
        # Try to get user_id from the session itself
        session_info = session_manager.get_session_context(session_id)
        user_id = session_info.get('user_id', 'unknown') if isinstance(session_info, dict) else 'unknown'
    
    # If still no user_id, try to get current system user
    if user_id == 'unknown':
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    try:
        if not session_manager.validate_session(session_id):
            result = {
                "success": False,
                "message": "Invalid or expired session"
            }
            log_tool_call(session_id, user_id, "get_session_summary", {"session_id": session_id}, result)
            return result
        
        # Get conversation history
        history = session_manager.get_conversation_history(session_id)
        
        # Analyze the history
        tool_counts = {}
        job_references = set()
        last_activity = None
        
        for entry in history:
            try:
                tool_data = eval(entry['content']) if isinstance(entry['content'], str) else entry['content']
                tool_name = tool_data.get('tool_name', 'Unknown')
                
                # Count tool usage
                tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1
                
                # Extract job references
                args = tool_data.get('arguments', {})
                if 'cluster_id' in args:
                    job_references.add(args['cluster_id'])
                
                # Track last activity
                if not last_activity or entry['timestamp'] > last_activity:
                    last_activity = entry['timestamp']
                    
            except Exception:
                continue
        
        # Create summary
        summary = {
            "session_id": session_id,
            "total_interactions": len(history),
            "tools_used": tool_counts,
            "jobs_referenced": list(job_references),
            "last_activity": last_activity,
            "session_info": session_manager.get_session_context(session_id)
        }
        
        result = {
            "success": True,
            "summary": summary
        }
        
        log_tool_call(session_id, user_id, "get_session_summary", {"session_id": session_id}, result)
        return result
        
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to get session summary: {str(e)}"
        }
        log_tool_call(session_id, user_id, "get_session_summary", {"session_id": session_id}, result)
        return result


# ===== CLUSTER AND POOL INFORMATION =====

def list_pools(tool_context=None) -> dict:
    """List available HTCondor pools."""
    try:
        # Get pool information from HTCondor configuration
        config = htcondor.param
        pool_info = []
        
        # Get current pool
        current_pool = config.get("COLLECTOR_HOST", "Unknown")
        pool_info.append({
            "name": "Default Pool",
            "collector_host": current_pool,
            "status": "Active",
            "description": "Primary HTCondor pool"
        })
        
        # Try to get additional pools from configuration
        try:
            # Look for additional collectors
            additional_collectors = config.get("SECONDARY_COLLECTOR_HOSTS", "")
            if additional_collectors:
                for i, collector in enumerate(additional_collectors.split(',')):
                    pool_info.append({
                        "name": f"Secondary Pool {i+1}",
                        "collector_host": collector.strip(),
                        "status": "Active",
                        "description": "Secondary HTCondor pool"
                    })
        except Exception:
            pass
        
        return {
            "success": True,
            "pools": pool_info,
            "total_pools": len(pool_info)
        }
    except Exception as e:
        return {"success": False, "message": f"Error listing pools: {str(e)}"}


def get_pool_status(tool_context=None) -> dict:
    """Get overall pool status and statistics."""
    try:
        schedd = htcondor.Schedd()
        
        # Get job statistics
        all_jobs = schedd.query("True", projection=["JobStatus", "Owner"])
        
        # Count jobs by status
        status_counts = defaultdict(int)
        user_counts = defaultdict(int)
        
        for ad in all_jobs:
            status = ad.get("JobStatus")
            owner = ad.get("Owner")
            
            if hasattr(status, "eval"):
                try:
                    status = status.eval()
                except Exception:
                    status = None
            
            if hasattr(owner, "eval"):
                try:
                    owner = owner.eval()
                except Exception:
                    owner = None
            
            status_counts[status] += 1
            user_counts[owner] += 1
        
        # Get machine information
        collector = htcondor.Collector()
        try:
            machines = collector.query(htcondor.AdTypes.Startd, "True", projection=["State", "Activity"])
            machine_stats = defaultdict(int)
            for machine in machines:
                state = machine.get("State")
                activity = machine.get("Activity")
                
                if hasattr(state, "eval"):
                    try:
                        state = state.eval()
                    except Exception:
                        state = "Unknown"
                
                if hasattr(activity, "eval"):
                    try:
                        activity = activity.eval()
                    except Exception:
                        activity = "Unknown"
                
                machine_stats[f"{state}_{activity}"] += 1
        except Exception:
            machine_stats = {"error": "Unable to retrieve machine information"}
        
        return {
            "success": True,
            "job_statistics": {
                "total_jobs": len(all_jobs),
                "by_status": dict(status_counts),
                "by_user": dict(user_counts)
            },
            "machine_statistics": dict(machine_stats),
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": f"Error getting pool status: {str(e)}"}


def list_machines(status: Optional[str] = None, tool_context=None) -> dict:
    """List execution machines with optional status filter."""
    try:
        collector = htcondor.Collector()
        
        # Build constraint based on status
        constraint = "True"
        if status:
            if status.lower() == "available":
                constraint = "State == 'Unclaimed'"
            elif status.lower() == "busy":
                constraint = "State == 'Claimed'"
            elif status.lower() == "offline":
                constraint = "State == 'Owner'"
        
        machines = collector.query(htcondor.AdTypes.Startd, constraint, 
                                 projection=["Name", "State", "Activity", "LoadAvg", "Memory", "Cpus"])
        
        machine_list = []
        for machine in machines:
            machine_info = {}
            for attr in ["Name", "State", "Activity", "LoadAvg", "Memory", "Cpus"]:
                v = machine.get(attr)
                if hasattr(v, "eval"):
                    try:
                        v = v.eval()
                    except Exception:
                        v = None
                machine_info[attr.lower()] = v
            machine_list.append(machine_info)
        
        return {
            "success": True,
            "machines": machine_list,
            "total_machines": len(machine_list),
            "filter": status or "all"
        }
    except Exception as e:
        return {"success": False, "message": f"Error listing machines: {str(e)}"}


def get_machine_status(machine_name: str, tool_context=None) -> dict:
    """Get detailed status for a specific machine."""
    try:
        collector = htcondor.Collector()
        machines = collector.query(htcondor.AdTypes.Startd, f'Name == "{machine_name}"')
        
        if not machines:
            return {"success": False, "message": f"Machine '{machine_name}' not found"}
        
        machine = machines[0]
        machine_info = {}
        
        # Get all available attributes
        for key, value in machine.items():
            if hasattr(value, "eval"):
                try:
                    machine_info[key] = value.eval()
                except Exception:
                    machine_info[key] = None
            else:
                machine_info[key] = value
        
        return {
            "success": True,
            "machine_name": machine_name,
            "status": machine_info
        }
    except Exception as e:
        return {"success": False, "message": f"Error getting machine status: {str(e)}"}


# ===== RESOURCE MONITORING =====

def get_resource_usage(cluster_id: Optional[int] = None, tool_context=None) -> dict:
    """Get resource usage statistics."""
    try:
        if cluster_id:
            # Get resource usage for specific job
            schedd = htcondor.Schedd()
            ads = schedd.query(f"ClusterId == {cluster_id}")
            if not ads:
                return {"success": False, "message": "Job not found"}
            
            ad = ads[0]
            usage = {}
            
            # Extract resource usage fields
            resource_fields = ["RemoteUserCpu", "RemoteSysCpu", "ImageSize", 
                             "MemoryUsage", "DiskUsage", "CommittedTime"]
            
            for field in resource_fields:
                v = ad.get(field)
                if hasattr(v, "eval"):
                    try:
                        v = v.eval()
                    except Exception:
                        v = None
                usage[field] = v
            
            return {
                "success": True,
                "cluster_id": cluster_id,
                "resource_usage": usage
            }
        else:
            # Get overall resource usage statistics
            schedd = htcondor.Schedd()
            all_jobs = schedd.query("True", projection=["RemoteUserCpu", "RemoteSysCpu", "ImageSize", "MemoryUsage"])
            
            total_cpu = 0
            total_memory = 0
            total_disk = 0
            job_count = 0
            
            for ad in all_jobs:
                cpu = ad.get("RemoteUserCpu", 0)
                memory = ad.get("MemoryUsage", 0)
                disk = ad.get("ImageSize", 0)
                
                if hasattr(cpu, "eval"):
                    try:
                        cpu = cpu.eval() or 0
                    except Exception:
                        cpu = 0
                
                if hasattr(memory, "eval"):
                    try:
                        memory = memory.eval() or 0
                    except Exception:
                        memory = 0
                
                if hasattr(disk, "eval"):
                    try:
                        disk = disk.eval() or 0
                    except Exception:
                        disk = 0
                
                total_cpu += cpu
                total_memory += memory
                total_disk += disk
                job_count += 1
            
            return {
                "success": True,
                "overall_usage": {
                    "total_cpu_time": total_cpu,
                    "total_memory_usage": total_memory,
                    "total_disk_usage": total_disk,
                    "active_jobs": job_count
                }
            }
    except Exception as e:
        return {"success": False, "message": f"Error getting resource usage: {str(e)}"}


def get_queue_stats(tool_context=None) -> dict:
    """Get queue statistics."""
    try:
        schedd = htcondor.Schedd()
        all_jobs = schedd.query("True", projection=["JobStatus"])
        
        status_counts = defaultdict(int)
        for ad in all_jobs:
            status = ad.get("JobStatus")
            if hasattr(status, "eval"):
                try:
                    status = status.eval()
                except Exception:
                    status = None
            
            status_counts[status] += 1
        
        # Convert status codes to readable names
        status_names = {
            1: "Idle",
            2: "Running", 
            3: "Removed",
            4: "Completed",
            5: "Held",
            6: "Transferring Output",
            7: "Suspended"
        }
        
        readable_stats = {}
        for status_code, count in status_counts.items():
            status_name = status_names.get(status_code, f"Status_{status_code}")
            readable_stats[status_name] = count
        
        return {
            "success": True,
            "queue_statistics": readable_stats,
            "total_jobs": len(all_jobs),
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": f"Error getting queue stats: {str(e)}"}


def get_system_load(tool_context=None) -> dict:
    """Get overall system load information."""
    try:
        collector = htcondor.Collector()
        machines = collector.query(htcondor.AdTypes.Startd, "True", 
                                 projection=["LoadAvg", "Memory", "Cpus", "State", "Activity"])
        
        total_cpus = 0
        total_memory = 0
        available_cpus = 0
        available_memory = 0
        machine_count = 0
        
        for machine in machines:
            cpus = machine.get("Cpus", 0)
            memory = machine.get("Memory", 0)
            state = machine.get("State")
            load_avg = machine.get("LoadAvg", 0)
            
            if hasattr(cpus, "eval"):
                try:
                    cpus = cpus.eval() or 0
                except Exception:
                    cpus = 0
            
            if hasattr(memory, "eval"):
                try:
                    memory = memory.eval() or 0
                except Exception:
                    memory = 0
            
            if hasattr(state, "eval"):
                try:
                    state = state.eval()
                except Exception:
                    state = "Unknown"
            
            if hasattr(load_avg, "eval"):
                try:
                    load_avg = load_avg.eval() or 0
                except Exception:
                    load_avg = 0
            
            total_cpus += cpus
            total_memory += memory
            machine_count += 1
            
            if state == "Unclaimed":
                available_cpus += cpus
                available_memory += memory
        
        return {
            "success": True,
            "system_load": {
                "total_machines": machine_count,
                "total_cpus": total_cpus,
                "total_memory_mb": total_memory,
                "available_cpus": available_cpus,
                "available_memory_mb": available_memory,
                "utilization_percent": ((total_cpus - available_cpus) / total_cpus * 100) if total_cpus > 0 else 0
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
    except Exception as e:
        return {"success": False, "message": f"Error getting system load: {str(e)}"}


# ===== REPORTING AND ANALYTICS =====

def generate_job_report(owner: Optional[str] = None, time_range: Optional[str] = None, tool_context=None) -> dict:
    """Generate comprehensive job report."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        schedd = htcondor.Schedd()
        
        # Build constraint
        constraints = []
        if owner:
            constraints.append(f'Owner == "{owner}"')
        if time_range:
            # Parse time range (e.g., "24h", "7d", "30d")
            if time_range.endswith('h'):
                hours = int(time_range[:-1])
                cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
            elif time_range.endswith('d'):
                days = int(time_range[:-1])
                cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
            else:
                cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
            
            constraints.append(f'QDate > {int(cutoff_time.timestamp())}')
        
        constraint = " and ".join(constraints) if constraints else "True"
        
        # Get jobs with extended attributes
        attrs = ["ClusterId", "ProcId", "JobStatus", "Owner", "QDate", "RemoteUserCpu", 
                "RemoteSysCpu", "ImageSize", "MemoryUsage", "CommittedTime"]
        jobs = schedd.query(constraint, projection=attrs)
        
        # Process job data
        job_data = []
        total_cpu = 0
        total_memory = 0
        status_counts = defaultdict(int)
        
        for ad in jobs:
            job_info = {}
            for attr in attrs:
                v = ad.get(attr)
                if hasattr(v, "eval"):
                    try:
                        v = v.eval()
                    except Exception:
                        v = None
                job_info[attr.lower()] = v
            
            # Calculate resource usage
            cpu_time = job_info.get("remoteusercpu", 0) or 0
            memory_usage = job_info.get("memoryusage", 0) or 0
            
            total_cpu += cpu_time
            total_memory += memory_usage
            
            status = job_info.get("jobstatus")
            status_counts[status] += 1
            
            job_data.append(job_info)
        
        # Generate report
        report = {
            "report_metadata": {
                "generated_at": datetime.datetime.now().isoformat(),
                "owner_filter": owner or "all",
                "time_range": time_range or "all",
                "total_jobs": len(job_data)
            },
            "summary": {
                "total_jobs": len(job_data),
                "status_distribution": dict(status_counts),
                "total_cpu_time": total_cpu,
                "total_memory_usage": total_memory,
                "average_cpu_per_job": total_cpu / len(job_data) if job_data else 0,
                "average_memory_per_job": total_memory / len(job_data) if job_data else 0
            },
            "job_details": job_data[:100]  # Limit to first 100 jobs to prevent large responses
        }
        
        result = {
            "success": True,
            "report": report
        }
        
        log_tool_call(session_id, user_id, "generate_job_report", {"owner": owner, "time_range": time_range}, result)
        return result
    except Exception as e:
        result = {"success": False, "message": f"Error generating job report: {str(e)}"}
        log_tool_call(session_id, user_id, "generate_job_report", {"owner": owner, "time_range": time_range}, result)
        return result


def get_utilization_stats(time_range: Optional[str] = "24h", tool_context=None) -> dict:
    """Get resource utilization statistics over time."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        schedd = htcondor.Schedd()
        
        # Calculate time range
        if time_range.endswith('h'):
            hours = int(time_range[:-1])
            cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
        elif time_range.endswith('d'):
            days = int(time_range[:-1])
            cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
        else:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
        
        # Get jobs in time range
        jobs = schedd.query(f'QDate > {int(cutoff_time.timestamp())}', 
                           projection=["JobStatus", "RemoteUserCpu", "MemoryUsage", "QDate", "CompletionDate"])
        
        # Calculate utilization metrics
        total_jobs = len(jobs)
        completed_jobs = 0
        total_cpu_time = 0
        total_memory_usage = 0
        avg_completion_time = 0
        
        completion_times = []
        
        for ad in jobs:
            status = ad.get("JobStatus")
            cpu_time = ad.get("RemoteUserCpu", 0)
            memory_usage = ad.get("MemoryUsage", 0)
            q_date = ad.get("QDate")
            completion_date = ad.get("CompletionDate")
            
            if hasattr(status, "eval"):
                try:
                    status = status.eval()
                except Exception:
                    status = None
            
            if hasattr(cpu_time, "eval"):
                try:
                    cpu_time = cpu_time.eval() or 0
                except Exception:
                    cpu_time = 0
            
            if hasattr(memory_usage, "eval"):
                try:
                    memory_usage = memory_usage.eval() or 0
                except Exception:
                    memory_usage = 0
            
            if hasattr(q_date, "eval"):
                try:
                    q_date = q_date.eval()
                except Exception:
                    q_date = None
            
            if hasattr(completion_date, "eval"):
                try:
                    completion_date = completion_date.eval()
                except Exception:
                    completion_date = None
            
            if status == 4:  # Completed
                completed_jobs += 1
                if q_date and completion_date:
                    completion_time = completion_date - q_date
                    completion_times.append(completion_time)
            
            total_cpu_time += cpu_time
            total_memory_usage += memory_usage
        
        # Calculate averages
        if completion_times:
            avg_completion_time = sum(completion_times) / len(completion_times)
        
        # Get current system capacity
        collector = htcondor.Collector()
        machines = collector.query(htcondor.AdTypes.Startd, "True", projection=["Cpus", "Memory"])
        
        total_cpus = 0
        total_memory = 0
        
        for machine in machines:
            cpus = machine.get("Cpus", 0)
            memory = machine.get("Memory", 0)
            
            if hasattr(cpus, "eval"):
                try:
                    cpus = cpus.eval() or 0
                except Exception:
                    cpus = 0
            
            if hasattr(memory, "eval"):
                try:
                    memory = memory.eval() or 0
                except Exception:
                    memory = 0
            
            total_cpus += cpus
            total_memory += memory
        
        # Calculate utilization percentages
        cpu_utilization = (total_cpu_time / (total_cpus * int(time_range[:-1]) * 3600)) * 100 if total_cpus > 0 else 0
        memory_utilization = (total_memory_usage / total_memory) * 100 if total_memory > 0 else 0
        
        result = {
            "success": True,
            "utilization_stats": {
                "time_range": time_range,
                "total_jobs": total_jobs,
                "completed_jobs": completed_jobs,
                "completion_rate": (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0,
                "total_cpu_time": total_cpu_time,
                "total_memory_usage": total_memory_usage,
                "average_completion_time": avg_completion_time,
                "cpu_utilization_percent": min(cpu_utilization, 100),
                "memory_utilization_percent": min(memory_utilization, 100),
                "system_capacity": {
                    "total_cpus": total_cpus,
                    "total_memory_mb": total_memory
                }
            },
            "timestamp": datetime.datetime.now().isoformat()
        }
        
        log_tool_call(session_id, user_id, "get_utilization_stats", {"time_range": time_range}, result)
        return result
    except Exception as e:
        result = {"success": False, "message": f"Error getting utilization stats: {str(e)}"}
        log_tool_call(session_id, user_id, "get_utilization_stats", {"time_range": time_range}, result)
        return result


def export_job_data(format: str = "json", filters: Optional[dict] = None, tool_context=None) -> dict:
    """Export job data in various formats."""
    # Get proper ADK context
    context_manager = get_context_manager()
    
    # Extract session info from tool_context if available
    session_id = None
    user_id = None
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Using proper ADK ToolContext
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
    else:
        # Fallback to old method
        session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        schedd = htcondor.Schedd()
        
        # Build constraint from filters
        constraints = []
        if filters:
            if "owner" in filters:
                constraints.append(f'Owner == "{filters["owner"]}"')
            if "status" in filters:
                status_map = {
                    "running": 2, "idle": 1, "held": 5,
                    "completed": 4, "removed": 3
                }
                status_code = status_map.get(filters["status"].lower())
                if status_code is not None:
                    constraints.append(f"JobStatus == {status_code}")
            if "min_cpu" in filters:
                constraints.append(f"RemoteUserCpu >= {filters['min_cpu']}")
        
        constraint = " and ".join(constraints) if constraints else "True"
        
        # Get job data
        attrs = ["ClusterId", "ProcId", "JobStatus", "Owner", "QDate", "RemoteUserCpu", 
                "MemoryUsage", "ImageSize", "CommittedTime"]
        jobs = schedd.query(constraint, projection=attrs)
        
        # Process job data
        job_data = []
        for ad in jobs:
            job_info = {}
            for attr in attrs:
                v = ad.get(attr)
                if hasattr(v, "eval"):
                    try:
                        v = v.eval()
                    except Exception:
                        v = None
                job_info[attr.lower()] = v
            job_data.append(job_info)
        
        # Format data based on requested format
        if format.lower() == "json":
            formatted_data = job_data
        elif format.lower() == "csv":
            # Convert to CSV format
            if job_data:
                headers = list(job_data[0].keys())
                csv_lines = [",".join(headers)]
                for job in job_data:
                    row = [str(job.get(header, "")) for header in headers]
                    csv_lines.append(",".join(row))
                formatted_data = "\n".join(csv_lines)
            else:
                formatted_data = ""
        elif format.lower() == "summary":
            # Generate summary statistics
            total_jobs = len(job_data)
            status_counts = defaultdict(int)
            total_cpu = 0
            total_memory = 0
            
            for job in job_data:
                status = job.get("jobstatus")
                status_counts[status] += 1
                
                cpu = job.get("remoteusercpu", 0) or 0
                memory = job.get("memoryusage", 0) or 0
                total_cpu += cpu
                total_memory += memory
            
            formatted_data = {
                "total_jobs": total_jobs,
                "status_distribution": dict(status_counts),
                "total_cpu_time": total_cpu,
                "total_memory_usage": total_memory,
                "average_cpu_per_job": total_cpu / total_jobs if total_jobs > 0 else 0
            }
        else:
            return {"success": False, "message": f"Unsupported format: {format}"}
        
        result = {
            "success": True,
            "format": format,
            "filters": filters or {},
            "total_jobs": len(job_data),
            "data": formatted_data
        }
        
        log_tool_call(session_id, user_id, "export_job_data", {"format": format, "filters": filters}, result)
        return result
    except Exception as e:
        result = {"success": False, "message": f"Error exporting job data: {str(e)}"}
        log_tool_call(session_id, user_id, "export_job_data", {"format": format, "filters": filters}, result)
        return result


# ===== NEW CONTEXT-AWARE TOOLS =====

def save_job_report(cluster_id: int, report_name: str, tool_context=None) -> dict:
    """Save a job report as an artifact using ADK Context."""
    # Get proper ADK context
    context_manager = get_context_manager()
    
    # Extract session info from tool_context if available
    session_id = None
    user_id = None
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Using proper ADK ToolContext
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
    else:
        # Fallback to old method
        session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get job status first
        job_status_result = get_job_status(cluster_id, tool_context)
        
        if not job_status_result.get("success"):
            result = {"success": False, "message": f"Failed to get job status: {job_status_result.get('message')}"}
            log_tool_call(session_id, user_id, "save_job_report", {"cluster_id": cluster_id, "report_name": report_name}, result)
            return result
        
        # Create report data
        report_data = {
            "cluster_id": cluster_id,
            "report_name": report_name,
            "generated_at": datetime.datetime.now().isoformat(),
            "job_status": job_status_result.get("job_status", {}),
            "user_id": user_id,
            "session_id": session_id
        }
        
        # Save as artifact using ADK Context
        if tool_context and hasattr(tool_context, 'save_htcondor_artifact'):
            artifact_id = tool_context.save_htcondor_artifact(report_name, report_data)
            result = {
                "success": True,
                "message": f"Job report saved as artifact",
                "artifact_id": artifact_id,
                "report_name": report_name,
                "cluster_id": cluster_id
            }
        else:
            # Fallback: save to context manager directly
            artifact_id = context_manager._save_artifact(session_id, report_name, report_data)
            result = {
                "success": True,
                "message": f"Job report saved as artifact (fallback)",
                "artifact_id": artifact_id,
                "report_name": report_name,
                "cluster_id": cluster_id
            }
        
        log_tool_call(session_id, user_id, "save_job_report", {"cluster_id": cluster_id, "report_name": report_name}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error saving job report: {str(e)}"}
        log_tool_call(session_id, user_id, "save_job_report", {"cluster_id": cluster_id, "report_name": report_name}, result)
        return result


def load_job_report(report_name: str, tool_context=None) -> dict:
    """Load a previously saved job report using ADK Context."""
    # Get proper ADK context
    context_manager = get_context_manager()
    
    # Extract session info from tool_context if available
    session_id = None
    user_id = None
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Using proper ADK ToolContext
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
    else:
        # Fallback to old method
        session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Load artifact using ADK Context
        if tool_context and hasattr(tool_context, 'load_htcondor_artifact'):
            artifact_data = tool_context.load_htcondor_artifact(report_name)
        else:
            # Fallback: load from context manager directly
            artifact_data = context_manager._load_artifact(session_id, report_name)
        
        if not artifact_data:
            result = {"success": False, "message": f"No report found with name: {report_name}"}
            log_tool_call(session_id, user_id, "load_job_report", {"report_name": report_name}, result)
            return result
        
        result = {
            "success": True,
            "message": f"Job report loaded successfully",
            "report_name": report_name,
            "artifact_data": artifact_data
        }
        
        log_tool_call(session_id, user_id, "load_job_report", {"report_name": report_name}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error loading job report: {str(e)}"}
        log_tool_call(session_id, user_id, "load_job_report", {"report_name": report_name}, result)
        return result


def search_job_memory(query: str, tool_context=None) -> dict:
    """Search memory for job-related information using ADK Context."""
    # Get proper ADK context
    context_manager = get_context_manager()
    
    # Extract session info from tool_context if available
    session_id = None
    user_id = None
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Using proper ADK ToolContext
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
    else:
        # Fallback to old method
        session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Search memory using ADK Context
        if tool_context and hasattr(tool_context, 'search_htcondor_memory'):
            search_results = tool_context.search_htcondor_memory(query)
        else:
            # Fallback: search from context manager directly
            search_results = context_manager._search_memory(user_id, query)
        
        result = {
            "success": True,
            "message": f"Memory search completed",
            "query": query,
            "results_count": len(search_results),
            "search_results": search_results
        }
        
        log_tool_call(session_id, user_id, "search_job_memory", {"query": query}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error searching memory: {str(e)}"}
        log_tool_call(session_id, user_id, "search_job_memory", {"query": query}, result)
        return result


def get_user_context_summary(tool_context=None) -> dict:
    """Get a comprehensive summary of the user's context and history."""
    # Get proper ADK context
    context_manager = get_context_manager()
    
    # Extract session info from tool_context if available
    session_id = None
    user_id = None
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Using proper ADK ToolContext
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
    else:
        # Fallback to old method
        session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get user memory
        user_memory = context_manager.get_user_memory(user_id)
        
        # Get current session context
        current_context = None
        if tool_context and hasattr(tool_context, 'htcondor_context'):
            current_context = tool_context.htcondor_context
        
        # Get recent job history
        recent_jobs = []
        if current_context and current_context.job_history:
            recent_jobs = current_context.job_history[-10:]  # Last 10 jobs
        
        # Get user preferences
        preferences = {}
        if current_context and current_context.preferences:
            preferences = current_context.preferences
        
        result = {
            "success": True,
            "message": f"User context summary retrieved",
            "user_id": user_id,
            "session_id": session_id,
            "current_jobs": current_context.current_jobs if current_context else [],
            "recent_job_history": recent_jobs,
            "user_preferences": preferences,
            "memory_entries": len(user_memory),
            "session_active": session_manager.validate_session(session_id) if session_id else False
        }
        
        log_tool_call(session_id, user_id, "get_user_context_summary", {}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error getting user context summary: {str(e)}"}
        log_tool_call(session_id, user_id, "get_user_context_summary", {}, result)
        return result


def add_to_memory(key: str, value: str, global_memory: bool = False, tool_context=None) -> dict:
    """Add information to memory using ADK Context."""
    # Get proper ADK context
    context_manager = get_context_manager()
    
    # Extract session info from tool_context if available
    session_id = None
    user_id = None
    if tool_context and hasattr(tool_context, 'htcondor_context'):
        # Using proper ADK ToolContext
        htcondor_ctx = tool_context.htcondor_context
        session_id = htcondor_ctx.session_id
        user_id = htcondor_ctx.user_id
    else:
        # Fallback to old method
        session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Add to memory using context manager
        context_manager.add_to_memory(user_id, key, value, global_memory)
        
        result = {
            "success": True,
            "message": f"Information added to {'global' if global_memory else 'user'} memory",
            "key": key,
            "value": value,
            "memory_type": "global" if global_memory else "user"
        }
        
        log_tool_call(session_id, user_id, "add_to_memory", {"key": key, "value": value, "global_memory": global_memory}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error adding to memory: {str(e)}"}
        log_tool_call(session_id, user_id, "add_to_memory", {"key": key, "value": value, "global_memory": global_memory}, result)
        return result


ADK_AF_TOOLS = {
    "list_jobs": FunctionTool(func=list_jobs),
    "get_job_status": FunctionTool(func=get_job_status),
    "submit_job": FunctionTool(func=submit_job),
    
    # Advanced Job Information
    "get_job_history": FunctionTool(func=get_job_history),
    
    # Session Management
    "list_user_sessions": FunctionTool(func=list_user_sessions),
    "continue_last_session": FunctionTool(func=continue_last_session),
    "get_session_history": FunctionTool(func=get_session_history),
    "get_session_summary": FunctionTool(func=get_session_summary),
    "get_user_conversation_memory": FunctionTool(func=get_user_conversation_memory),
    
    # Reporting and Analytics
    "generate_job_report": FunctionTool(func=generate_job_report),
    "get_utilization_stats": FunctionTool(func=get_utilization_stats),
    "export_job_data": FunctionTool(func=export_job_data),
    
    # Context-Aware Tools (ADK Context Integration)
    "save_job_report": FunctionTool(func=save_job_report),
    "load_job_report": FunctionTool(func=load_job_report),
    "search_job_memory": FunctionTool(func=search_job_memory),
    "get_user_context_summary": FunctionTool(func=get_user_context_summary),
    "add_to_memory": FunctionTool(func=add_to_memory),
}


@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    logging.info("Received list_tools request.")
    schemas = []
    for name, inst in ADK_AF_TOOLS.items():
        try:
        if not inst.name:
            inst.name = name
            logging.info(f"Converting tool schema for: {name}")
        schema = adk_to_mcp_tool_type(inst)
        schemas.append(schema)
            logging.info(f"Successfully converted tool schema for: {name}")
        except Exception as e:
            logging.error(f"Error converting tool schema for '{name}': {e}", exc_info=True)
            # Skip this tool if it fails to convert
            continue
    return schemas


@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    logging.info(f"call_tool for '{name}' args: {arguments}")
    
    # Create a copy of arguments to avoid modifying the original
    tool_args = arguments.copy()
    
    # Extract session context from arguments if present (but don't remove required parameters)
    # Note: If no session_id is provided, the tool functions will automatically create one
    session_id = tool_args.pop('session_id', None)
    tool_context = {'session_id': session_id} if session_id else None
    
    logging.info(f"Extracted session_id: {session_id}, tool_context: {tool_context}")
    
    if name in ADK_AF_TOOLS:
        inst = ADK_AF_TOOLS[name]
        try:
            # Add tool_context to arguments
            if tool_context:
                tool_args['tool_context'] = tool_context
            
            resp = await inst.run_async(args=tool_args, tool_context=tool_context)
            logging.info(f"Tool '{name}' success.")
            return [mcp_types.TextContent(type="text", text=json.dumps(resp, indent=2))]
        except Exception as e:
            logging.error(f"Error executing '{name}': {e}", exc_info=True)
            return [mcp_types.TextContent(type="text", text=json.dumps({
                "success": False,
                "message": str(e)
            }))]
    else:
        return [mcp_types.TextContent(type="text", text=json.dumps({
            "success": False,
            "message": f"Tool '{name}' not found"
        }))]


async def run_mcp_stdio_server():
    async with mcp.server.stdio.stdio_server() as (r, w):
        logging.info("Starting MCP stdio server...")
        await app.run(r, w, InitializationOptions(
            server_name=app.name,
            server_version="0.1.0",
            capabilities=app.get_capabilities(notification_options=NotificationOptions(), experimental_capabilities={}),
        ))
        logging.info("STDIO session ended.")


if __name__ == "__main__":
    logging.info("Launching MCP Server...")
    try:
        asyncio.run(run_mcp_stdio_server())
    except KeyboardInterrupt:
        logging.info("Server stopped by user.")
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
    finally:
        logging.info("Server exiting.")