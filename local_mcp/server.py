import asyncio
import json
import logging
import os
import datetime
import getpass
import sqlite3
import pandas as pd
import numpy as np
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

# Import simplified session context management - handle both relative and absolute imports
try:
    from .session_context_simple import get_simplified_session_context_manager
    from .htcondor_dataframe import HTCondorDataFrame
except ImportError:
    # When running server.py directly, use absolute import
    import sys
    sys.path.append(os.path.dirname(os.path.dirname(__file__)))
    from local_mcp.session_context_simple import get_simplified_session_context_manager
    from local_mcp.htcondor_dataframe import HTCondorDataFrame

load_dotenv()

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "mcp_server_activity.log")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE_PATH, mode="w")],
)

logging.info("Creating MCP Server instance for HTCondor...")
app = Server("htcondor-mcp-server")

# Initialize simplified session context management
session_context_manager = get_simplified_session_context_manager()

# Global DataFrame management
import threading
_global_dataframe_instance = None
_global_dataframe_lock = threading.Lock()

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
                WHERE s.user_id = ? AND s.is_active = TRUE
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
    logging.debug(f"Tool call: {tool_name} for session {session_id}")
    if session_id and session_context_manager.validate_session(session_id):
        try:
            tool_call_data = {
                "tool_name": tool_name,
                "arguments": arguments,
                "result": result
            }
            session_context_manager.add_message(session_id, "tool_call", str(tool_call_data))
            logging.debug(f"Tool call logged for session {session_id}")
        except Exception as e:
            logging.error(f"Failed to log tool call: {e}")
    else:
        logging.warning(f"No valid session_id for tool call: {tool_name}")

def list_jobs(owner: Optional[str] = None, status: Optional[str] = None, limit: int = 10, tool_context=None) -> dict:
    """List jobs using global DataFrame."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe(owner=owner)
        
        if len(df) == 0:
            result = {
                "success": True,
                "jobs": [],
                "total_jobs": 0
            }
            log_tool_call(session_id, user_id, "list_jobs", {"owner": owner, "status": status, "limit": limit}, result)
            return result
        
        # Apply status filter if specified
        if status is not None:
            status_map = {
                "running": 2, "idle": 1, "held": 5,
                "completed": 4, "removed": 3,
                "transferring_output": 6, "suspended": 7,
            }
            status_code = status_map.get(status.lower())
            if status_code is not None and 'jobstatus' in df.columns:
                df = df[df['jobstatus'] == status_code]
        
        # Convert DataFrame to list of job dictionaries
        jobs = []
        status_code_map = {
            1: "Idle",
            2: "Running", 
            3: "Removed",
            4: "Completed",
            5: "Held",
            6: "Transferring Output",
            7: "Suspended"
        }
        
        for _, row in df.head(limit).iterrows():
            job_info = {
                "ClusterId": row.get('clusterid'),
                "ProcId": row.get('procid'),
                "JobStatus": row.get('jobstatus'),
                "Owner": row.get('owner'),
                "Status": status_code_map.get(row.get('jobstatus'), "Unknown")
            }
            jobs.append(job_info)
        
        result = {
            "success": True,
            "jobs": jobs,
            "total_jobs": len(df)
        }
        
        log_tool_call(session_id, user_id, "list_jobs", {"owner": owner, "status": status, "limit": limit}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error listing jobs: {str(e)}"}
        log_tool_call(session_id, user_id, "list_jobs", {"owner": owner, "status": status, "limit": limit}, result)
        return result


def get_job_status(cluster_id: int, tool_context=None) -> dict:
    """Get job status using global DataFrame."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe()
        
        if len(df) == 0:
            result = {"success": False, "message": "No job data available"}
            log_tool_call(session_id, user_id, "get_job_status", {"cluster_id": cluster_id}, result)
            return result
        
        # Filter by cluster ID (convert to string for comparison)
        job_df = df[df['clusterid'].astype(str) == str(cluster_id)]
        
        if len(job_df) == 0:
            result = {"success": False, "message": "Job not found"}
            log_tool_call(session_id, user_id, "get_job_status", {"cluster_id": cluster_id}, result)
            return result
        
        # Get the first job (should be the main one)
        row = job_df.iloc[0]
        job_info = {}
        
        # Map DataFrame columns to display names
        field_mapping = {
            "clusterid": "Cluster ID",
            "procid": "Process ID", 
            "jobstatus": "Job Status",
            "owner": "Owner",
            "cmd": "Command",
            "arguments": "Arguments",
            "iwd": "Working Directory",
            "jobuniverse": "Job Universe",
            "qdate": "Queue Date",
            "jobstartdate": "Job Start Date",
            "jobcurrentstartdate": "Current Start Date",
            "remotehost": "Execution Host",
            "remotesusercpu": "CPU Time Used",
            "remotesyscpu": "System CPU Time",
            "memoryusage": "Memory Used",
            "diskusage": "Disk Used",
            "requestcpus": "Requested CPUs",
            "requestmemory": "Requested Memory",
            "requestdisk": "Requested Disk",
            "jobprio": "Job Priority",
            "numjobstarts": "Number of Starts",
            "jobruncount": "Run Count",
            "exitstatus": "Exit Status",
            "wallclockcheckpoint": "Wall Clock Time",
            "in": "Input File",
            "out": "Output File",
            "err": "Error File",
            "userlog": "Log File"
        }
        
        for col_name, display_name in field_mapping.items():
            if col_name in row.index and pd.notna(row[col_name]):
                v = row[col_name]
                
                # Format special fields
                if col_name == "jobstatus":
                    status_map = {
                        1: "Idle", 2: "Running", 3: "Removed", 4: "Completed",
                        5: "Held", 6: "Transferring Output", 7: "Suspended"
                    }
                    v = f"{v} ({status_map.get(v, 'Unknown')})"
                elif col_name == "jobuniverse":
                    universe_map = {
                        1: "Standard", 2: "Pipes", 3: "Linda", 4: "PVM",
                        5: "Vanilla", 6: "Scheduler", 7: "MPI", 9: "Grid",
                        10: "Java", 11: "Parallel", 12: "Local", 13: "Docker"
                    }
                    v = f"{v} ({universe_map.get(v, 'Unknown')})"
                elif col_name in ["qdate", "jobstartdate", "jobcurrentstartdate"] and v:
                    # Convert Unix timestamp to readable format
                    try:
                        v = datetime.datetime.fromtimestamp(v).isoformat()
                    except (ValueError, TypeError):
                        pass
                elif col_name in ["requestmemory", "memoryusage"] and v:
                    # Format memory with units
                    try:
                        v_num = float(v)
                        if v_num >= 1024:
                            v = f"{v} MB ({v_num//1024:.1f} GB)"
                        else:
                            v = f"{v} MB"
                    except (ValueError, TypeError):
                        v = f"{v} MB"
                elif col_name in ["requestdisk", "diskusage"] and v:
                    # Format disk with units
                    try:
                        v_num = float(v)
                        if v_num >= 1024:
                            v = f"{v} MB ({v_num//1024:.1f} GB)"
                        else:
                            v = f"{v} MB"
                    except (ValueError, TypeError):
                        v = f"{v} MB"
                elif col_name == "arguments" and not v:
                    v = "(none)"
                elif col_name in ["in", "out", "err"] and not v:
                    v = "(default)"
                elif col_name == "wallclockcheckpoint" and v:
                    # Convert seconds to hours:minutes:seconds
                    try:
                        hours = int(v // 3600)
                        minutes = int((v % 3600) // 60)
                        seconds = int(v % 60)
                        v = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    except (ValueError, TypeError):
                        pass
                
                job_info[display_name] = v
        
        # Helper function to convert numpy types to JSON-serializable types
        def convert_numpy_types(obj):
            """Convert numpy types to JSON-serializable types"""
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            else:
                return obj
        
        result = {
            "success": True,
            "cluster_id": cluster_id,
            "job_status": convert_numpy_types(job_info),
            "note": "Most useful job information extracted from global DataFrame"
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
    """Get job execution history using global DataFrame."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe()
        
        if len(df) == 0:
            result = {"success": False, "message": "No job data available"}
            log_tool_call(session_id, user_id, "get_job_history", {"cluster_id": cluster_id, "limit": limit}, result)
            return result
        
        # Filter by cluster ID (convert to string for comparison)
        job_df = df[df['clusterid'].astype(str) == str(cluster_id)]
        
        if len(job_df) == 0:
            result = {"success": False, "message": "Job not found"}
            log_tool_call(session_id, user_id, "get_job_history", {"cluster_id": cluster_id, "limit": limit}, result)
            return result
        
        # Get the first job (should be the main one)
        row = job_df.iloc[0]
        
        # Get actual job timestamps and create realistic history
        q_date = row.get('qdate')  # Queue date (submission time)
        job_start_date = row.get('jobstartdate')  # When job started
        job_current_start_date = row.get('jobcurrentstartdate')  # Current start time
        completion_date = row.get('completiondate')  # When job completed
        job_status = row.get('jobstatus')
        
        history_events = []
        
        # Add submission event
        if pd.notna(q_date):
            history_events.append({
                "timestamp": datetime.datetime.fromtimestamp(q_date).isoformat(),
                "event": "Job submitted",
                "status": "Idle"
            })
        
        # Add start event
        if pd.notna(job_start_date) or pd.notna(job_current_start_date):
            start_time = job_current_start_date if pd.notna(job_current_start_date) else job_start_date
            history_events.append({
                "timestamp": datetime.datetime.fromtimestamp(start_time).isoformat(),
                "event": "Job started",
                "status": "Running"
            })
        
        # Add completion event if job is completed
        if job_status == 4 and pd.notna(completion_date):  # Completed
            history_events.append({
                "timestamp": datetime.datetime.fromtimestamp(completion_date).isoformat(),
                "event": "Job completed",
                "status": "Completed"
            })
        
        # If no real timestamps, provide current status info
        if not history_events:
            status_map = {
                1: "Idle", 2: "Running", 3: "Removed", 4: "Completed",
                5: "Held", 6: "Transferring Output", 7: "Suspended"
            }
            current_status = status_map.get(job_status, "Unknown")
            history_events.append({
                "timestamp": datetime.datetime.now().isoformat(),
                "event": "Current status",
                "status": current_status
            })
        
        # Helper function to convert numpy types to JSON-serializable types
        def convert_numpy_types(obj):
            """Convert numpy types to JSON-serializable types"""
            import numpy as np
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            else:
                return obj
        
        result = {
            "success": True,
            "cluster_id": cluster_id,
            "current_status": convert_numpy_types(job_status),
            "history_events": convert_numpy_types(history_events[:limit]),
            "total_events": len(history_events),
            "note": "History based on actual job timestamps from global DataFrame"
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
    # Get simplified session context manager
    scm = get_simplified_session_context_manager()
    
    session_id, _ = get_session_context(tool_context)  # We don't need user_id here since we're creating a session
    
    try:
        session_id = scm.create_session(user_id, metadata)
        
        # Automatically initialize global DataFrame for new session
        dataframe_result = initialize_global_dataframe()
        
        result = {
            "success": True,
            "session_id": session_id,
            "user_id": user_id,
            "message": f"Session created successfully for user {user_id}",
            "dataframe_initialized": dataframe_result["success"],
            "dataframe_info": dataframe_result.get("data", {})
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

def start_fresh_session(user_id: Optional[str] = None, metadata: Optional[dict] = None, tool_context=None) -> dict:
    """Start a completely fresh session, ignoring any existing sessions."""
    if user_id is None:
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    # Get simplified session context manager
    scm = get_simplified_session_context_manager()
    
    try:
        session_id = scm.create_session(user_id, metadata or {})
        
        # Automatically initialize global DataFrame for fresh session
        dataframe_result = initialize_global_dataframe()
        
        result = {
            "success": True,
            "session_id": session_id,
            "user_id": user_id,
            "message": f"Fresh session created successfully for user {user_id}",
            "note": "This is a new session, not continuing any previous session",
            "dataframe_initialized": dataframe_result["success"],
            "dataframe_info": dataframe_result.get("data", {})
        }
        
        log_tool_call(session_id, user_id, "start_fresh_session", {"user_id": user_id, "metadata": metadata}, result)
        return result
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to create fresh session: {str(e)}"
        }
        log_tool_call(None, user_id, "start_fresh_session", {"user_id": user_id, "metadata": metadata}, result)
        return result

def get_session_info(session_id: str, tool_context=None) -> dict:
    """Get information about a session."""
    # Get simplified session context manager
    scm = get_simplified_session_context_manager()
    
    _, user_id = get_session_context(tool_context)  # We don't need session_id here since it's a parameter
    
    try:
        if not scm.validate_session(session_id):
            return {
                "success": False,
                "message": "Invalid or expired session"
            }
        
        context = scm.get_session_context(session_id)
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
    # Get simplified session context manager
    scm = get_simplified_session_context_manager()
    
    _, user_id = get_session_context(tool_context)  # We don't need session_id here since it's a parameter
    
    try:
        if scm.validate_session(session_id):
            scm.deactivate_session(session_id)
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
    # Get simplified session context manager
    scm = get_simplified_session_context_manager()
    
    # Get user_id from session context, but use the provided session_id
    _, user_id = get_session_context(tool_context)
    if user_id is None:
        # Try to get user_id from the session itself
        session_info = scm.get_session_context(session_id)
        user_id = session_info.get('user_id', 'unknown') if isinstance(session_info, dict) else 'unknown'
    
    # If still no user_id, try to get current system user
    if user_id == 'unknown':
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    try:
        if not scm.validate_session(session_id):
            result = {
                "success": False,
                "message": "Invalid or expired session"
            }
            log_tool_call(session_id, user_id, "get_session_history", {"session_id": session_id}, result)
            return result
        
        # Get conversation history from database
        history = scm.get_conversation_history(session_id)
        
        # Parse and format the history
        formatted_history = []
        for entry in history:
            try:
                # Parse the tool call data - use ast.literal_eval for safer parsing
                import ast
                content_str = entry['content']
                if isinstance(content_str, str):
                    # Try to parse as literal eval first (safer)
                    try:
                        tool_data = ast.literal_eval(content_str)
                    except (ValueError, SyntaxError):
                        # Fallback to eval if literal_eval fails
                        tool_data = eval(content_str)
                else:
                    tool_data = content_str
                
                formatted_entry = {
                    "timestamp": entry['timestamp'],
                    "tool_name": tool_data.get('tool_name', 'Unknown'),
                    "arguments": tool_data.get('arguments', {}),
                    "result_summary": str(tool_data.get('result', {}))[:200] + "..." if len(str(tool_data.get('result', {}))) > 200 else str(tool_data.get('result', {}))
                }
                formatted_history.append(formatted_entry)
            except Exception as e:
                # Skip malformed entries but log the error
                logging.warning(f"Failed to parse conversation entry: {e}")
                continue
        
        result = {
            "success": True,
            "session_id": session_id,
            "total_entries": len(formatted_history),
            "conversation_history": formatted_history,
            "session_info": scm.get_session_context(session_id)
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
    # Get simplified session context manager
    scm = get_simplified_session_context_manager()
    
    if user_id is None:
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    try:
        last_session = get_last_active_session(user_id)
        
        if last_session:
            session_id = last_session[0]
            session_info = scm.get_session_context(session_id)
            
            # Automatically initialize global DataFrame when continuing session
            dataframe_result = initialize_global_dataframe()
            
            result = {
                "success": True,
                "message": f"Continuing session {session_id}",
                "session_id": session_id,
                "session_info": session_info,
                "dataframe_initialized": dataframe_result["success"],
                "dataframe_info": dataframe_result.get("data", {})
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

def continue_specific_session(session_id: str, user_id: Optional[str] = None, tool_context=None) -> dict:
    """Continue a specific session by session ID."""
    if user_id is None:
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    logging.info(f"continue_specific_session called with session_id: {session_id}, user_id: {user_id}")
    
    try:
        # Get simplified session context manager
        scm = get_simplified_session_context_manager()
        
        # Validate the session
        if not scm.validate_session(session_id):
            result = {
                "success": False,
                "message": "Invalid or expired session"
            }
            log_tool_call(session_id, user_id, "continue_specific_session", {"session_id": session_id, "user_id": user_id}, result)
            return result
        
        # Get session context
        session_context = scm.get_session_context(session_id)
        
        # Update session activity
        scm.update_session_activity(session_id)
        
        # Automatically initialize global DataFrame when continuing specific session
        dataframe_result = initialize_global_dataframe()
        
        result = {
            "success": True,
            "session_id": session_id,
            "user_id": user_id,
            "session_context": session_context,
            "message": f"Successfully switched to session {session_id}",
            "dataframe_initialized": dataframe_result["success"],
            "dataframe_info": dataframe_result.get("data", {})
        }
        
        log_tool_call(session_id, user_id, "continue_specific_session", {"session_id": session_id, "user_id": user_id}, result)
        return result
        
    except Exception as e:
        result = {
            "success": False,
            "message": f"Failed to continue specific session: {str(e)}"
        }
        log_tool_call(session_id, user_id, "continue_specific_session", {"session_id": session_id, "user_id": user_id}, result)
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
        
        # Get simplified session context manager
        scm = get_simplified_session_context_manager()
        
        # Get conversation history from all sessions
        all_conversations = []
        for session in sessions:
            session_id = session['session_id']
            history = scm.get_conversation_history(session_id, limit=limit)
            
            for entry in history:
                try:
                    # Parse the tool call data - use ast.literal_eval for safer parsing
                    import ast
                    content_str = entry['content']
                    if isinstance(content_str, str):
                        # Try to parse as literal eval first (safer)
                        try:
                            tool_data = ast.literal_eval(content_str)
                        except (ValueError, SyntaxError):
                            # Fallback to eval if literal_eval fails
                            tool_data = eval(content_str)
                    else:
                        tool_data = content_str
                    
                    conversation_entry = {
                        "session_id": session_id,
                        "timestamp": entry['timestamp'],
                        "tool_name": tool_data.get('tool_name', 'Unknown'),
                        "arguments": tool_data.get('arguments', {}),
                        "result_summary": str(tool_data.get('result', {}))[:200] + "..." if len(str(tool_data.get('result', {}))) > 200 else str(tool_data.get('result', {}))
                    }
                    all_conversations.append(conversation_entry)
                except Exception as e:
                    # Skip malformed entries but log the error
                    logging.warning(f"Failed to parse conversation entry in memory: {e}")
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
    # Get simplified session context manager
    scm = get_simplified_session_context_manager()
    
    # Get user_id from session context, but use the provided session_id
    _, user_id = get_session_context(tool_context)
    if user_id is None:
        # Try to get user_id from the session itself
        session_info = scm.get_session_context(session_id)
        user_id = session_info.get('user_id', 'unknown') if isinstance(session_info, dict) else 'unknown'
    
    # If still no user_id, try to get current system user
    if user_id == 'unknown':
        try:
            user_id = getpass.getuser()
        except Exception:
            user_id = os.getenv('USER', os.getenv('USERNAME', 'unknown'))
    
    try:
        if not scm.validate_session(session_id):
            result = {
                "success": False,
                "message": "Invalid or expired session"
            }
            log_tool_call(session_id, user_id, "get_session_summary", {"session_id": session_id}, result)
            return result
        
        # Get conversation history
        history = scm.get_conversation_history(session_id)
        
        # Analyze the history
        tool_counts = {}
        job_references = set()
        last_activity = None
        
        for entry in history:
            try:
                # Parse the tool call data - use ast.literal_eval for safer parsing
                import ast
                content_str = entry['content']
                if isinstance(content_str, str):
                    # Try to parse as literal eval first (safer)
                    try:
                        tool_data = ast.literal_eval(content_str)
                    except (ValueError, SyntaxError):
                        # Fallback to eval if literal_eval fails
                        tool_data = eval(content_str)
                else:
                    tool_data = content_str
                
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
                    
            except Exception as e:
                # Skip malformed entries but log the error
                logging.warning(f"Failed to parse conversation entry in summary: {e}")
                continue
        
        # Create summary
        summary = {
            "session_id": session_id,
            "total_interactions": len(history),
            "tools_used": tool_counts,
            "jobs_referenced": list(job_references),
            "last_activity": last_activity,
            "session_info": scm.get_session_context(session_id)
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




# ===== REPORTING AND ANALYTICS =====

def generate_job_report(owner: Optional[str] = None, time_range: Optional[str] = None, tool_context=None) -> dict:
    """Generate comprehensive job report using global DataFrame."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe(time_range=time_range, owner=owner)
        
        if len(df) == 0:
            result = {
                "success": True,
                "report": {
                    "report_metadata": {
                        "generated_at": datetime.datetime.now().isoformat(),
                        "owner_filter": owner or "all",
                        "time_range": time_range or "all",
                        "total_jobs": 0
                    },
                    "summary": {
                        "total_jobs": 0,
                        "status_distribution": {},
                        "total_cpu_time": 0,
                        "total_memory_usage": 0,
                        "average_cpu_per_job": 0,
                        "average_memory_per_job": 0
                    },
                    "job_details": []
                }
            }
            log_tool_call(session_id, user_id, "generate_job_report", {"owner": owner, "time_range": time_range}, result)
            return result
        
        # Process job data
        job_data = []
        total_cpu = 0
        total_memory = 0
        status_counts = defaultdict(int)
        
        for _, row in df.iterrows():
            job_info = {
                "clusterid": row.get('clusterid'),
                "procid": row.get('procid'),
                "jobstatus": row.get('jobstatus'),
                "owner": row.get('owner'),
                "qdate": row.get('qdate'),
                "remotesusercpu": row.get('remotesusercpu'),
                "remotesyscpu": row.get('remotesyscpu'),
                "imagesize": row.get('imagesize'),
                "memoryusage": row.get('memoryusage'),
                "committedtime": row.get('committedtime')
            }
            
            # Calculate resource usage
            cpu_time = pd.to_numeric(job_info.get("remotesusercpu"), errors='coerce')
            memory_usage = pd.to_numeric(job_info.get("memoryusage"), errors='coerce')
            cpu_time = 0 if pd.isna(cpu_time) else cpu_time
            memory_usage = 0 if pd.isna(memory_usage) else memory_usage
            
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
    """Get resource utilization statistics using global DataFrame."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe(time_range=time_range)
        
        if len(df) == 0:
            result = {
                "success": True,
                "utilization_stats": {
                    "time_range": time_range,
                    "total_jobs": 0,
                    "completed_jobs": 0,
                    "completion_rate": 0,
                    "total_cpu_time": 0,
                    "total_memory_usage": 0,
                    "average_completion_time": 0,
                    "cpu_utilization": 0,
                    "memory_utilization": 0,
                    "note": "No job data available for the specified time range"
                }
            }
            log_tool_call(session_id, user_id, "get_utilization_stats", {"time_range": time_range}, result)
            return result
        
        # Calculate utilization metrics
        total_jobs = len(df)
        completed_jobs = 0
        total_cpu_time = 0
        total_memory_usage = 0
        avg_completion_time = 0
        
        completion_times = []
        
        for _, row in df.iterrows():
            status = row.get('jobstatus')
            cpu_time = pd.to_numeric(row.get('remotesusercpu'), errors='coerce')
            memory_usage = pd.to_numeric(row.get('memoryusage'), errors='coerce')
            cpu_time = 0 if pd.isna(cpu_time) else cpu_time
            memory_usage = 0 if pd.isna(memory_usage) else memory_usage
            q_date = row.get('qdate')
            completion_date = row.get('completiondate')
            
            if status == 4:  # Completed
                completed_jobs += 1
                if pd.notna(q_date) and pd.notna(completion_date):
                    completion_time = completion_date - q_date
                    completion_times.append(completion_time)
            
            total_cpu_time += cpu_time
            total_memory_usage += memory_usage
        
        # Calculate averages
        if completion_times:
            avg_completion_time = sum(completion_times) / len(completion_times)
        
        # Get current system capacity (still need to query collector for this)
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
        time_hours = int(time_range[:-1]) if time_range.endswith('h') else int(time_range[:-1]) * 24
        cpu_utilization = (total_cpu_time / (total_cpus * time_hours * 3600)) * 100 if total_cpus > 0 else 0
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
    """Export job data in various formats using global DataFrame."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe()
        
        if len(df) == 0:
            result = {
                "success": True,
                "format": format,
                "filters": filters or {},
                "total_jobs": 0,
                "data": [] if format.lower() == "json" else "" if format.lower() == "csv" else {}
            }
            log_tool_call(session_id, user_id, "export_job_data", {"format": format, "filters": filters}, result)
            return result
        
        # Apply filters
        if filters:
            if "owner" in filters:
                df = df[df['owner'] == filters["owner"]]
            if "status" in filters:
                status_map = {
                    "running": 2, "idle": 1, "held": 5,
                    "completed": 4, "removed": 3
                }
                status_code = status_map.get(filters["status"].lower())
                if status_code is not None:
                    df = df[df['jobstatus'] == status_code]
            if "min_cpu" in filters:
                df = df[pd.to_numeric(df['remotesusercpu'], errors='coerce').replace([np.inf, -np.inf], np.nan).fillna(0) >= filters['min_cpu']]
        
        # Convert DataFrame to list of dictionaries
        job_data = []
        for _, row in df.iterrows():
            job_info = {
                "clusterid": row.get('clusterid'),
                "procid": row.get('procid'),
                "jobstatus": row.get('jobstatus'),
                "owner": row.get('owner'),
                "qdate": row.get('qdate'),
                "remotesusercpu": row.get('remotesusercpu'),
                "memoryusage": row.get('memoryusage'),
                "imagesize": row.get('imagesize'),
                "committedtime": row.get('committedtime')
            }
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
                
                cpu = pd.to_numeric(job.get("remotesusercpu"), errors='coerce')
                memory = pd.to_numeric(job.get("memoryusage"), errors='coerce')
                cpu = 0 if pd.isna(cpu) else cpu
                memory = 0 if pd.isna(memory) else memory
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


def generate_advanced_job_report(
    owner: Optional[str] = None, 
    time_range: Optional[str] = "7d",
    report_type: str = "comprehensive",
    include_trends: bool = True,
    include_predictions: bool = False,
    output_format: str = "text",
    tool_context=None
) -> dict:
    """Generate advanced job report with comprehensive analytics using global DataFrame."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe(time_range=time_range, owner=owner)
        
        if len(df) == 0:
            result = {"success": True, "message": "No job data available for the specified criteria", "data": {}}
            log_tool_call(session_id, user_id, "generate_advanced_job_report", 
                         {"owner": owner, "time_range": time_range, "report_type": report_type}, result)
            return result
        
        # Process DataFrame data with enhanced metrics
        total_memory = pd.to_numeric(df['memoryusage'], errors='coerce').fillna(0).sum() if 'memoryusage' in df.columns else 0
        total_disk = pd.to_numeric(df['imagesize'], errors='coerce').fillna(0).sum() if 'imagesize' in df.columns else 0
        
        # Status counts
        status_counts = df['jobstatus'].value_counts().to_dict() if 'jobstatus' in df.columns else {}
        
        # Owner statistics
        owner_stats = {}
        if 'owner' in df.columns:
            for owner in df['owner'].unique():
                owner_df = df[df['owner'] == owner]
                # Convert to numeric values to avoid string division issues
                memory_sum = pd.to_numeric(owner_df['memoryusage'], errors='coerce').fillna(0).sum() if 'memoryusage' in owner_df.columns else 0
                
                owner_stats[owner] = {
                    "jobs": len(owner_df),
                    "memory": memory_sum,
                    "completed": len(owner_df[owner_df['jobstatus'] == 4]) if 'jobstatus' in owner_df.columns else 0,
                    "failed": len(owner_df[owner_df['jobstatus'].isin([3, 5, 7])]) if 'jobstatus' in owner_df.columns else 0
                }
        
        # Time distribution analysis
        hourly_distribution = {}
        daily_distribution = {}
        if 'qdate' in df.columns:
            # Convert timestamps to datetime for analysis
            df['qdate_datetime'] = pd.to_datetime(df['qdate'], unit='s', errors='coerce')
            hourly_distribution = df['qdate_datetime'].dt.hour.value_counts().to_dict()
            daily_distribution = df['qdate_datetime'].dt.date.value_counts().to_dict()
            daily_distribution = {str(k): v for k, v in daily_distribution.items()}
        
        # Completion times
        completion_times = []
        if 'qdate' in df.columns and 'completiondate' in df.columns:
            completed_jobs = df[df['jobstatus'] == 4]
            completion_times = (completed_jobs['completiondate'] - completed_jobs['qdate']).dropna().tolist()
        
        # Failure reasons
        failure_reasons = {}
        if 'exitcode' in df.columns:
            failed_jobs = df[df['jobstatus'].isin([3, 5, 7])]
            # Filter out exit code 0.0 (successful completion) from failure analysis
            failed_jobs_with_exit_codes = failed_jobs[failed_jobs['exitcode'] != 0.0]
            failed_jobs_with_exit_codes = failed_jobs_with_exit_codes[failed_jobs_with_exit_codes['exitcode'] != 0]
            failure_reasons = failed_jobs_with_exit_codes['exitcode'].value_counts().to_dict()
        
        # Resource efficiency analysis
        resource_efficiency = []
        if 'memoryusage' in df.columns and 'requestmemory' in df.columns:
            efficiency_df = df[df['requestmemory'] > 0]
            for _, row in efficiency_df.iterrows():
                try:
                    # Convert to numeric values, handling any string values
                    memoryusage = pd.to_numeric(row['memoryusage'], errors='coerce') or 0
                    requestmemory = pd.to_numeric(row['requestmemory'], errors='coerce') or 1
                    
                    memory_efficiency = memoryusage / requestmemory if requestmemory > 0 else 0
                    resource_efficiency.append({
                        "cluster_id": row.get('clusterid'),
                        "memory_efficiency": memory_efficiency,
                        "overall_efficiency": memory_efficiency
                    })
                except (ValueError, TypeError, ZeroDivisionError):
                    # Skip this row if there are conversion issues
                    continue
        
        # Calculate advanced metrics
        avg_completion_time = sum(completion_times) / len(completion_times) if completion_times else 0
        
        # Enhanced job status analysis
        total_jobs = len(df)
        completed_jobs = status_counts.get(4, 0)
        running_jobs = status_counts.get(2, 0)
        idle_jobs = status_counts.get(1, 0)
        removed_jobs = status_counts.get(3, 0)
        held_jobs = status_counts.get(5, 0)
        suspended_jobs = status_counts.get(7, 0)
        
        # Calculate final state jobs (completed + failed)
        final_jobs = completed_jobs + removed_jobs + held_jobs + suspended_jobs
        
        # Enhanced success rate calculation (only final states)
        success_rate = (completed_jobs / final_jobs * 100) if final_jobs > 0 else 0
        
        # Additional metrics
        active_jobs = running_jobs + idle_jobs
        active_jobs_percentage = (active_jobs / total_jobs * 100) if total_jobs > 0 else 0
        failure_rate = ((removed_jobs + held_jobs + suspended_jobs) / total_jobs * 100) if total_jobs > 0 else 0
        completion_rate = (completed_jobs / total_jobs * 100) if total_jobs > 0 else 0
        
        # Resource utilization analysis
        avg_memory_per_job = total_memory / total_jobs if total_jobs > 0 else 0
        avg_disk_per_job = total_disk / total_jobs if total_jobs > 0 else 0
        
        # Trend analysis (if requested)
        trends = {}
        if include_trends and len(daily_distribution) > 1:
            sorted_days = sorted(daily_distribution.items())
            job_counts = [count for _, count in sorted_days]
            
            # Simple linear trend
            if len(job_counts) > 1:
                x = list(range(len(job_counts)))
                y = job_counts
                slope = (len(x) * sum(i * j for i, j in zip(x, y)) - sum(x) * sum(y)) / (len(x) * sum(i * i for i in x) - sum(x) ** 2)
                trends["job_submission_trend"] = "increasing" if slope > 0 else "decreasing" if slope < 0 else "stable"
                trends["trend_slope"] = slope
        
        # Predictive analytics (if requested)
        predictions = {}
        if include_predictions and len(daily_distribution) > 3:
            # Simple moving average prediction
            sorted_days = sorted(daily_distribution.items())
            recent_counts = [count for _, count in sorted_days[-3:]]
            avg_recent = sum(recent_counts) / len(recent_counts)
            predictions["predicted_jobs_next_day"] = int(avg_recent)
            predictions["confidence_level"] = "medium"
        
        # Performance insights
        performance_insights = []
        if resource_efficiency:
            avg_efficiency = sum(r["overall_efficiency"] for r in resource_efficiency) / len(resource_efficiency)
            if avg_efficiency < 0.5:
                performance_insights.append("Low resource utilization detected - consider optimizing job requirements")
            if len(failure_reasons) > 0:
                top_failure = max(failure_reasons.items(), key=lambda x: x[1])
                performance_insights.append(f"Most common failure reason: Exit code {top_failure[0]} ({top_failure[1]} occurrences)")
        
        # Calculate cutoff time for analysis duration
        if time_range:
            if time_range.endswith('h'):
                hours = int(time_range[:-1])
                cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
            elif time_range.endswith('d'):
                days = int(time_range[:-1])
                cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
            elif time_range.endswith('w'):
                weeks = int(time_range[:-1])
                cutoff_time = datetime.datetime.now() - datetime.timedelta(weeks=weeks)
            else:
                cutoff_time = datetime.datetime.now() - datetime.timedelta(days=7)
        else:
            cutoff_time = datetime.datetime.now() - datetime.timedelta(days=7)
        
        # Generate comprehensive report
        report = {
            "report_metadata": {
                "generated_at": datetime.datetime.now().isoformat(),
                "report_type": report_type,
                "owner_filter": owner or "all",
                "time_range": time_range,
                "total_jobs": total_jobs,
                "analysis_duration": f"{(datetime.datetime.now() - cutoff_time).days} days"
            },
            "summary": {
                "total_jobs": total_jobs,
                "status_distribution": dict(status_counts),
                "success_rate_percent": success_rate,
                "active_jobs": active_jobs,
                "active_jobs_percentage": active_jobs_percentage,
                "failure_rate_percent": failure_rate,
                "completion_rate_percent": completion_rate,
                "final_jobs": final_jobs,
                "total_memory_usage_mb": total_memory,
                "total_disk_usage_mb": total_disk,
                "average_completion_time_seconds": avg_completion_time,
                "average_memory_per_job": avg_memory_per_job,
                "average_disk_per_job": avg_disk_per_job
            },
            "owner_analysis": {
                owner: {
                    "total_jobs": stats["jobs"],
                    "completed_jobs": stats["completed"],
                    "failed_jobs": stats["failed"],
                    "success_rate": (stats["completed"] / stats["jobs"] * 100) if stats["jobs"] > 0 else 0,
                    "total_memory_usage": stats["memory"]
                }
                for owner, stats in owner_stats.items()
            },
            "temporal_analysis": {
                "hourly_distribution": dict(hourly_distribution),
                "daily_distribution": dict(daily_distribution),
                "peak_hour": max(hourly_distribution.items(), key=lambda x: x[1])[0] if hourly_distribution else None,
                "peak_day": max(daily_distribution.items(), key=lambda x: x[1])[0] if daily_distribution else None
            },
            "failure_analysis": {
                "failure_reasons": dict(failure_reasons),
                "total_failures": sum(failure_reasons.values()),
                "failure_rate_percent": (sum(failure_reasons.values()) / total_jobs * 100) if total_jobs > 0 else 0
            },
            "resource_efficiency": {
                "average_efficiency": sum(r["overall_efficiency"] for r in resource_efficiency) / len(resource_efficiency) if resource_efficiency else 0,
                "efficiency_distribution": {
                    "high": len([r for r in resource_efficiency if r["overall_efficiency"] > 0.8]),
                    "medium": len([r for r in resource_efficiency if 0.5 <= r["overall_efficiency"] <= 0.8]),
                    "low": len([r for r in resource_efficiency if r["overall_efficiency"] < 0.5])
                }
            }
        }
        
        if trends:
            report["trends"] = trends
        if predictions:
            report["predictions"] = predictions
        if performance_insights:
            report["performance_insights"] = performance_insights
        
        # Create job_data from DataFrame for detailed reports
        job_data = []
        if report_type in ["comprehensive", "summary"]:
            # Convert DataFrame rows to dictionaries
            sample_df = df.head(200 if report_type == "comprehensive" else 50)
            job_data = sample_df.to_dict('records')
        
        # Include detailed job data based on report type
        if report_type == "comprehensive":
            report["job_details"] = job_data[:200]  # Limit to prevent large responses
        elif report_type == "summary":
            report["job_details"] = job_data[:50]
        else:  # minimal
            report["job_details"] = []
        
        # Helper function to convert numpy types to JSON-serializable types
        def convert_numpy_types(obj):
            """Convert numpy types to JSON-serializable types"""
            import numpy as np
            import pandas as pd
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, pd.Timestamp):
                return obj.isoformat()
            elif pd.isna(obj):  # Handle NaT, NaN, etc.
                return None
            elif isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            else:
                return obj
        
        # Process output format
        if output_format.lower() == "json":
            formatted_data = convert_numpy_types(report)
        elif output_format.lower() == "csv":
            # Convert job details to CSV format
            if report.get("job_details"):
                headers = list(report["job_details"][0].keys())
                csv_lines = [",".join(headers)]
                for job in report["job_details"]:
                    row = [str(job.get(header, "")) for header in headers]
                    csv_lines.append(",".join(row))
                formatted_data = "\n".join(csv_lines)
            else:
                formatted_data = "No job details available for CSV export"
        elif output_format.lower() == "summary":
            # Return only summary statistics
            formatted_data = {
                "summary": report.get("summary", {}),
                "owner_analysis": report.get("owner_analysis", {}),
                "performance_insights": report.get("performance_insights", [])
            }
        elif output_format.lower() == "text":
            # Convert report to human-readable text format
            text_lines = []
            text_lines.append("=== ADVANCED JOB REPORT ===")
            text_lines.append(f"Generated: {report['report_metadata']['generated_at']}")
            text_lines.append(f"Time Range: {report['report_metadata']['time_range']}")
            text_lines.append(f"Report Type: {report['report_metadata']['report_type']}")
            text_lines.append("")
            
            # Summary section
            summary = report.get('summary', {})
            text_lines.append("--- SUMMARY ---")
            text_lines.append(f"Total Jobs: {summary.get('total_jobs', 'N/A')}")
            text_lines.append(f"Success Rate: {summary.get('success_rate_percent', 'N/A'):.2f}% (of final jobs)")
            text_lines.append(f"Active Jobs: {summary.get('active_jobs', 'N/A')} ({summary.get('active_jobs_percentage', 'N/A'):.2f}%)")
            text_lines.append(f"Failure Rate: {summary.get('failure_rate_percent', 'N/A'):.2f}%")
            text_lines.append(f"Completion Rate: {summary.get('completion_rate_percent', 'N/A'):.2f}%")
            text_lines.append(f"Final Jobs: {summary.get('final_jobs', 'N/A')} (completed + failed)")
            text_lines.append(f"Total Memory Usage: {summary.get('total_memory_usage_mb', 'N/A'):.2f} MB")
            text_lines.append(f"Average Completion Time: {summary.get('average_completion_time_seconds', 'N/A'):.2f} seconds")
            text_lines.append("")
            
            # Enhanced status distribution with descriptions
            if summary.get('status_distribution'):
                text_lines.append("--- STATUS DISTRIBUTION ---")
                status_descriptions = {
                    1: "Idle (waiting)",
                    2: "Running",
                    3: "Removed",
                    4: "Completed",
                    5: "Held",
                    7: "Suspended"
                }
                # Show all possible statuses, even if count is 0
                for status in sorted(status_descriptions.keys()):
                    count = summary['status_distribution'].get(status, 0)
                    desc = status_descriptions.get(status, "Unknown")
                    percentage = (count / summary.get('total_jobs', 1) * 100) if summary.get('total_jobs', 0) > 0 else 0
                    text_lines.append(f"Status {status} ({desc}): {count} jobs ({percentage:.2f}%)")
                text_lines.append("")
            
            # Owner analysis
            if report.get('owner_analysis'):
                text_lines.append("--- OWNER ANALYSIS ---")
                for owner, stats in report['owner_analysis'].items():
                    text_lines.append(f"Owner: {owner}")
                    text_lines.append(f"  Total Jobs: {stats.get('total_jobs', 'N/A')}")
                    text_lines.append(f"  Success Rate: {stats.get('success_rate', 'N/A'):.2f}%")
                    text_lines.append("")
            
            # Performance insights
            if report.get('performance_insights'):
                text_lines.append("--- PERFORMANCE INSIGHTS ---")
                for insight in report['performance_insights']:
                    text_lines.append(f"• {insight}")
                text_lines.append("")
            
            formatted_data = "\n".join(text_lines)
        else:
            return {"success": False, "message": f"Unsupported output format: {output_format}"}
        
        result = {
            "success": True,
            "output_format": output_format,
            "report": convert_numpy_types(formatted_data)
        }
        
        log_tool_call(session_id, user_id, "generate_advanced_job_report", 
                     {"owner": owner, "time_range": time_range, "report_type": report_type}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error generating advanced job report: {str(e)}"}
        log_tool_call(session_id, user_id, "generate_advanced_job_report", 
                     {"owner": owner, "time_range": time_range, "report_type": report_type}, result)
        return result


def generate_queue_wait_time_histogram(
    time_range: Optional[str] = "30d",
    bin_count: int = 10,
    owner: Optional[str] = None,
    status_filter: Optional[str] = None,
    tool_context=None
) -> dict:
    """Generate histogram of queue wait times for jobs using global DataFrame."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe(time_range=time_range, owner=owner)
        
        if len(df) == 0:
            result = {
                "success": True,
                "message": "No job data available for the specified criteria",
                "time_range": time_range,
                "total_jobs_analyzed": 0,
                "jobs_with_wait_times": 0,
                "histogram": {},
                "statistics": {}
            }
            log_tool_call(session_id, user_id, "generate_queue_wait_time_histogram", 
                         {"time_range": time_range, "bin_count": bin_count, "owner": owner, "status_filter": status_filter}, result)
            return result
        
        # Apply status filter if specified
        if status_filter:
            status_map = {
                "running": 2, "idle": 1, "held": 5,
                "completed": 4, "removed": 3, "suspended": 7
            }
            status_code = status_map.get(status_filter.lower())
            if status_code is not None and 'jobstatus' in df.columns:
                df = df[df['jobstatus'] == status_code]
        
        # Calculate wait times from DataFrame
        wait_times = []
        job_details = []
        
        # Check if required columns exist
        required_columns = ['qdate', 'jobstartdate', 'jobcurrentstartdate']
        if not all(col in df.columns for col in required_columns):
            result = {
                "success": True,
                "message": "Required columns for wait time calculation not available in DataFrame",
                "time_range": time_range,
                "total_jobs_analyzed": len(df),
                "jobs_with_wait_times": 0,
                "histogram": {},
                "statistics": {}
            }
            log_tool_call(session_id, user_id, "generate_queue_wait_time_histogram", 
                         {"time_range": time_range, "bin_count": bin_count, "owner": owner, "status_filter": status_filter}, result)
            return result
        
        # Calculate wait times for each job
        for _, row in df.iterrows():
            q_date = row.get('qdate')
            job_start_date = row.get('jobstartdate')
            job_current_start_date = row.get('jobcurrentstartdate')
            
            # Use current start date if available, otherwise use first start date
            start_date = job_current_start_date if pd.notna(job_current_start_date) else job_start_date
            
            if pd.notna(q_date) and pd.notna(start_date) and start_date > q_date:
                wait_time = start_date - q_date  # Wait time in seconds
                wait_times.append(wait_time)
                
                job_details.append({
                    "cluster_id": row.get('clusterid'),
                    "proc_id": row.get('procid'),
                    "owner": row.get('owner'),
                    "status": row.get('jobstatus'),
                    "queue_date": q_date,
                    "start_date": start_date,
                    "wait_time_seconds": wait_time,
                    "wait_time_minutes": wait_time / 60,
                    "wait_time_hours": wait_time / 3600
                })
        
        if not wait_times:
            result = {
                "success": True,
                "message": "No jobs with valid wait time data found in the specified time range",
                "time_range": time_range,
                "total_jobs_analyzed": len(df),
                "jobs_with_wait_times": 0,
                "histogram": {},
                "statistics": {}
            }
            log_tool_call(session_id, user_id, "generate_queue_wait_time_histogram", 
                         {"time_range": time_range, "bin_count": bin_count, "owner": owner, "status_filter": status_filter}, result)
            return result
        
        # Calculate statistics
        wait_times.sort()
        total_jobs = len(wait_times)
        min_wait = min(wait_times)
        max_wait = max(wait_times)
        avg_wait = sum(wait_times) / total_jobs
        median_wait = wait_times[total_jobs // 2] if total_jobs % 2 == 1 else (wait_times[total_jobs // 2 - 1] + wait_times[total_jobs // 2]) / 2
        
        # Calculate percentiles
        p25 = wait_times[int(total_jobs * 0.25)]
        p75 = wait_times[int(total_jobs * 0.75)]
        p90 = wait_times[int(total_jobs * 0.90)]
        p95 = wait_times[int(total_jobs * 0.95)]
        p99 = wait_times[int(total_jobs * 0.99)]
        
        # Create histogram bins
        bin_width = (max_wait - min_wait) / bin_count if max_wait > min_wait else 1
        bins = []
        bin_counts = [0] * bin_count
        
        for i in range(bin_count):
            bin_start = min_wait + (i * bin_width)
            bin_end = min_wait + ((i + 1) * bin_width) if i < bin_count - 1 else max_wait + 1
            bins.append({
                "bin_number": i + 1,
                "range_start_seconds": bin_start,
                "range_end_seconds": bin_end,
                "range_start_minutes": bin_start / 60,
                "range_end_minutes": bin_end / 60,
                "range_start_hours": bin_start / 3600,
                "range_end_hours": bin_end / 3600,
                "count": 0,
                "percentage": 0
            })
        
        # Populate histogram
        for wait_time in wait_times:
            bin_index = min(int((wait_time - min_wait) / bin_width), bin_count - 1)
            bin_counts[bin_index] += 1
            bins[bin_index]["count"] += 1
        
        # Calculate percentages
        for bin_data in bins:
            bin_data["percentage"] = (bin_data["count"] / total_jobs) * 100
        
        # Create summary statistics
        statistics = {
            "total_jobs_analyzed": len(df),
            "jobs_with_wait_times": total_jobs,
            "min_wait_time_seconds": min_wait,
            "max_wait_time_seconds": max_wait,
            "avg_wait_time_seconds": avg_wait,
            "median_wait_time_seconds": median_wait,
            "min_wait_time_minutes": min_wait / 60,
            "max_wait_time_minutes": max_wait / 60,
            "avg_wait_time_minutes": avg_wait / 60,
            "median_wait_time_minutes": median_wait / 60,
            "min_wait_time_hours": min_wait / 3600,
            "max_wait_time_hours": max_wait / 3600,
            "avg_wait_time_hours": avg_wait / 3600,
            "median_wait_time_hours": median_wait / 3600,
            "percentiles": {
                "25th_percentile_seconds": p25,
                "75th_percentile_seconds": p75,
                "90th_percentile_seconds": p90,
                "95th_percentile_seconds": p95,
                "99th_percentile_seconds": p99,
                "25th_percentile_minutes": p25 / 60,
                "75th_percentile_minutes": p75 / 60,
                "90th_percentile_minutes": p90 / 60,
                "95th_percentile_minutes": p95 / 60,
                "99th_percentile_minutes": p99 / 60,
                "25th_percentile_hours": p25 / 3600,
                "75th_percentile_hours": p75 / 3600,
                "90th_percentile_hours": p90 / 3600,
                "95th_percentile_hours": p95 / 3600,
                "99th_percentile_hours": p99 / 3600
            }
        }
        
        # Helper function to convert numpy types to JSON-serializable types
        def convert_numpy_types(obj):
            """Convert numpy types to JSON-serializable types"""
            if isinstance(obj, np.integer):
                return int(obj)
            elif isinstance(obj, np.floating):
                return float(obj)
            elif isinstance(obj, np.ndarray):
                return obj.tolist()
            elif isinstance(obj, dict):
                return {key: convert_numpy_types(value) for key, value in obj.items()}
            elif isinstance(obj, list):
                return [convert_numpy_types(item) for item in obj]
            else:
                return obj
        
        # Create result
        result = {
            "success": True,
            "time_range": time_range,
            "bin_count": bin_count,
            "owner_filter": owner or "all",
            "status_filter": status_filter or "all",
            "statistics": convert_numpy_types(statistics),
            "histogram": convert_numpy_types({
                "bins": bins,
                "total_jobs": total_jobs,
                "bin_width_seconds": bin_width,
                "bin_width_minutes": bin_width / 60,
                "bin_width_hours": bin_width / 3600
            }),
            "sample_jobs": convert_numpy_types(job_details[:20])  # Include first 20 jobs as examples
        }
        
        log_tool_call(session_id, user_id, "generate_queue_wait_time_histogram", 
                     {"time_range": time_range, "bin_count": bin_count, "owner": owner, "status_filter": status_filter}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error generating queue wait time histogram: {str(e)}"}
        log_tool_call(session_id, user_id, "generate_queue_wait_time_histogram", 
                     {"time_range": time_range, "bin_count": bin_count, "owner": owner, "status_filter": status_filter}, result)
        return result


# ===== GLOBAL DATAFRAME MANAGEMENT =====

def get_global_dataframe():
    """Get the global DataFrame instance, creating it if it doesn't exist"""
    global _global_dataframe_instance, _global_dataframe_lock
    
    with _global_dataframe_lock:
        if _global_dataframe_instance is None:
            logging.info("Creating new global DataFrame instance")
            _global_dataframe_instance = HTCondorDataFrame()
        return _global_dataframe_instance

def initialize_global_dataframe(time_range: Optional[str] = None, force_update: bool = False) -> dict:
    """Initialize the global DataFrame and return basic information"""
    
    try:
        # Get or create global DataFrame instance
        htcondor_df = get_global_dataframe()
        
        # Get all jobs data
        df = htcondor_df.get_all_jobs(time_range=time_range, force_update=force_update)
        
        if len(df) == 0:
            return {"success": True, "message": "No job data available", "data": {}}
        
        # Get summary statistics
        stats = htcondor_df.get_summary_stats()
        
        return {
            "success": True,
            "message": f"Initialized global DataFrame with {len(df)} jobs",
            "data": {
                "total_jobs": len(df),
                "current_queue_jobs": stats.get('current_queue_jobs', 0),
                "historical_jobs": stats.get('historical_jobs', 0),
                "success_rate": stats.get('success_rate', 0),
                "unique_owners": stats.get('unique_owners', 0),
                "dataframe_columns": len(df.columns),
                "time_range": time_range,
                "force_update": force_update
            }
        }
        
    except Exception as e:
        return {"success": False, "message": f"Error initializing global DataFrame: {str(e)}"}

def refresh_global_dataframe(time_range: Optional[str] = None) -> dict:
    """Force refresh the global DataFrame"""
    return initialize_global_dataframe(time_range=time_range, force_update=True)

def get_dataframe_status() -> dict:
    """Get the status of the global DataFrame"""
    global _global_dataframe_instance
    
    try:
        if _global_dataframe_instance is None:
            return {
                "success": True,
                "dataframe_exists": False,
                "message": "Global DataFrame not initialized"
            }
        
        # Check if DataFrame has data
        df = _global_dataframe_instance.df
        if df is None or len(df) == 0:
            return {
                "success": True,
                "dataframe_exists": True,
                "dataframe_has_data": False,
                "message": "Global DataFrame exists but has no data"
            }
        
        # Calculate time since last update
        time_since_update = None
        needs_update = False
        if _global_dataframe_instance.last_update:
            time_since_update = (datetime.datetime.now() - _global_dataframe_instance.last_update).seconds
            needs_update = time_since_update >= _global_dataframe_instance.update_interval
        
        # Get basic info
        stats = _global_dataframe_instance.get_summary_stats()
        return {
            "success": True,
            "dataframe_exists": True,
            "dataframe_has_data": True,
            "total_jobs": len(df),
            "current_queue_jobs": stats.get('current_queue_jobs', 0),
            "historical_jobs": stats.get('historical_jobs', 0),
            "success_rate": stats.get('success_rate', 0),
            "unique_owners": stats.get('unique_owners', 0),
            "dataframe_columns": len(df.columns),
            "last_update": _global_dataframe_instance.last_update.isoformat() if _global_dataframe_instance.last_update else None,
            "time_since_update_seconds": time_since_update,
            "needs_update": needs_update,
            "update_interval_seconds": _global_dataframe_instance.update_interval,
            "message": f"Global DataFrame ready with {len(df)} jobs (updated {time_since_update}s ago)"
        }
        
    except Exception as e:
        return {"success": False, "message": f"Error checking DataFrame status: {str(e)}"}

# ===== NEW CONTEXT-AWARE TOOLS =====

def get_jobs_from_global_dataframe(time_range: Optional[str] = None, owner: Optional[str] = None) -> pd.DataFrame:
    """Get jobs from global DataFrame with optional filtering"""
    try:
        # Get global DataFrame
        htcondor_df = get_global_dataframe()
        
        # Check if DataFrame exists and has data
        if htcondor_df.df is None or len(htcondor_df.df) == 0:
            # Only call get_all_jobs() if DataFrame is empty
            logging.info("Global DataFrame is empty, initializing...")
            df = htcondor_df.get_all_jobs(force_update=False)
        else:
            # Check if DataFrame needs updating based on update interval
            needs_update = False
            if htcondor_df.last_update:
                time_since_update = (datetime.datetime.now() - htcondor_df.last_update).seconds
                needs_update = time_since_update >= htcondor_df.update_interval
            
            if needs_update:
                logging.info(f"Global DataFrame is {time_since_update}s old, updating...")
                df = htcondor_df.get_all_jobs(force_update=False)
            else:
                # Use existing DataFrame directly (much more efficient)
                logging.info(f"Using existing global DataFrame (updated {time_since_update}s ago)")
                df = htcondor_df.df.copy()  # Make a copy to avoid modifying the original
        
        if len(df) == 0:
            return pd.DataFrame()
        
        # Apply time range filter if specified
        if time_range and 'qdate' in df.columns:
            if time_range.endswith('h'):
                hours = int(time_range[:-1])
                cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=hours)
            elif time_range.endswith('d'):
                days = int(time_range[:-1])
                cutoff_time = datetime.datetime.now() - datetime.timedelta(days=days)
            else:
                cutoff_time = datetime.datetime.now() - datetime.timedelta(hours=24)
            cutoff_timestamp = int(cutoff_time.timestamp())
            df = df[pd.to_numeric(df['qdate'], errors='coerce').fillna(0) >= cutoff_timestamp]
        
        # Apply owner filter if specified
        if owner and 'owner' in df.columns:
            df = df[df['owner'] == owner]
        
        return df
        
    except Exception as e:
        logging.error(f"Error getting jobs from global DataFrame: {e}")
        return pd.DataFrame()

def get_dataframe_status_tool(tool_context=None) -> dict:
    """Get the status of the global DataFrame (tool version with session logging)"""
    
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        result = get_dataframe_status()
        log_tool_call(session_id, user_id, "get_dataframe_status", {}, result)
        return result
    except Exception as e:
        result = {"success": False, "message": f"Error getting DataFrame status: {str(e)}"}
        log_tool_call(session_id, user_id, "get_dataframe_status", {}, result)
        return result

def refresh_dataframe_tool(time_range: Optional[str] = None, tool_context=None) -> dict:
    """Force refresh the global DataFrame (tool version with session logging)"""
    
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        result = refresh_global_dataframe(time_range=time_range)
        log_tool_call(session_id, user_id, "refresh_dataframe", {"time_range": time_range}, result)
        return result
    except Exception as e:
        result = {"success": False, "message": f"Error refreshing DataFrame: {str(e)}"}
        log_tool_call(session_id, user_id, "refresh_dataframe", {"time_range": time_range}, result)
        return result


def analyze_memory_usage_by_owner(
    time_range: Optional[str] = None,
    include_efficiency: bool = True,
    include_details: bool = True,
    tool_context=None
) -> dict:
    """Analyze memory usage by job owner including requested vs actual memory usage."""
    session_id, user_id = ensure_session_exists(tool_context)
    
    try:
        # Get jobs from global DataFrame
        df = get_jobs_from_global_dataframe(time_range=time_range)
        
        if len(df) == 0:
            result = {
                "success": True,
                "message": "No job data available for memory analysis",
                "time_range": time_range,
                "total_jobs": 0,
                "memory_analysis": {}
            }
            log_tool_call(session_id, user_id, "analyze_memory_usage_by_owner", 
                         {"time_range": time_range, "include_efficiency": include_efficiency, "include_details": include_details}, result)
            return result
        
        # Check if required memory columns exist
        required_columns = ['owner', 'memoryusage', 'requestmemory']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            result = {
                "success": False,
                "message": f"Missing required columns for memory analysis: {missing_columns}",
                "available_columns": list(df.columns)
            }
            log_tool_call(session_id, user_id, "analyze_memory_usage_by_owner", 
                         {"time_range": time_range, "include_efficiency": include_efficiency, "include_details": include_details}, result)
            return result
        
        # Group by owner and calculate memory statistics
        owner_memory_stats = {}
        total_requested_memory = 0
        total_actual_memory = 0
        total_jobs = 0
        
        for owner in df['owner'].unique():
            owner_df = df[df['owner'] == owner]
            owner_jobs = len(owner_df)
            
            # Convert memory values to numeric, handling any string values
            actual_memory = pd.to_numeric(owner_df['memoryusage'], errors='coerce').fillna(0)
            requested_memory = pd.to_numeric(owner_df['requestmemory'], errors='coerce').fillna(0)
            
            # Calculate totals
            owner_actual_total = actual_memory.sum()
            owner_requested_total = requested_memory.sum()
            
            # Calculate averages
            owner_actual_avg = actual_memory.mean() if len(actual_memory) > 0 else 0
            owner_requested_avg = requested_memory.mean() if len(requested_memory) > 0 else 0
            
            # Calculate efficiency (actual/requested ratio)
            efficiency_ratio = (owner_actual_total / owner_requested_total * 100) if owner_requested_total > 0 else 0
            
            # Calculate memory waste (requested - actual)
            memory_waste = owner_requested_total - owner_actual_total
            
            # Get memory distribution
            actual_memory_stats = {
                "min": float(actual_memory.min()) if len(actual_memory) > 0 else 0,
                "max": float(actual_memory.max()) if len(actual_memory) > 0 else 0,
                "median": float(actual_memory.median()) if len(actual_memory) > 0 else 0,
                "std": float(actual_memory.std()) if len(actual_memory) > 0 else 0
            }
            
            requested_memory_stats = {
                "min": float(requested_memory.min()) if len(requested_memory) > 0 else 0,
                "max": float(requested_memory.max()) if len(requested_memory) > 0 else 0,
                "median": float(requested_memory.median()) if len(requested_memory) > 0 else 0,
                "std": float(requested_memory.std()) if len(requested_memory) > 0 else 0
            }
            
            # Create owner statistics
            owner_stats = {
                "total_jobs": owner_jobs,
                "total_actual_memory_mb": float(owner_actual_total),
                "total_requested_memory_mb": float(owner_requested_total),
                "average_actual_memory_mb": float(owner_actual_avg),
                "average_requested_memory_mb": float(owner_requested_avg),
                "memory_efficiency_percent": float(efficiency_ratio),
                "memory_waste_mb": float(memory_waste),
                "actual_memory_stats": actual_memory_stats,
                "requested_memory_stats": requested_memory_stats
            }
            
            # Add efficiency insights
            if include_efficiency:
                if efficiency_ratio < 50:
                    owner_stats["efficiency_insight"] = "Low efficiency - significant over-allocation"
                elif efficiency_ratio < 80:
                    owner_stats["efficiency_insight"] = "Moderate efficiency - some over-allocation"
                elif efficiency_ratio > 120:
                    owner_stats["efficiency_insight"] = "High usage - potential under-allocation risk"
                else:
                    owner_stats["efficiency_insight"] = "Good efficiency - well-allocated memory"
            
            owner_memory_stats[owner] = owner_stats
            
            # Update totals
            total_requested_memory += owner_requested_total
            total_actual_memory += owner_actual_total
            total_jobs += owner_jobs
        
        # Sort owners by total actual memory usage (descending)
        sorted_owners = sorted(
            owner_memory_stats.items(),
            key=lambda x: x[1]['total_actual_memory_mb'],
            reverse=True
        )
        
        # Create rankings
        rankings = []
        for i, (owner, stats) in enumerate(sorted_owners, 1):
            ranking_entry = {
                "rank": i,
                "owner": owner,
                "total_actual_memory_mb": stats['total_actual_memory_mb'],
                "total_requested_memory_mb": stats['total_requested_memory_mb'],
                "memory_efficiency_percent": stats['memory_efficiency_percent'],
                "total_jobs": stats['total_jobs'],
                "percentage_of_total_memory": (stats['total_actual_memory_mb'] / total_actual_memory * 100) if total_actual_memory > 0 else 0
            }
            rankings.append(ranking_entry)
        
        # Calculate overall statistics
        overall_efficiency = (total_actual_memory / total_requested_memory * 100) if total_requested_memory > 0 else 0
        overall_memory_waste = total_requested_memory - total_actual_memory
        
        # Create detailed analysis
        analysis = {
            "summary": {
                "total_jobs": total_jobs,
                "total_owners": len(owner_memory_stats),
                "total_actual_memory_mb": float(total_actual_memory),
                "total_requested_memory_mb": float(total_requested_memory),
                "overall_memory_efficiency_percent": float(overall_efficiency),
                "overall_memory_waste_mb": float(overall_memory_waste),
                "average_actual_memory_per_job": float(total_actual_memory / total_jobs) if total_jobs > 0 else 0,
                "average_requested_memory_per_job": float(total_requested_memory / total_jobs) if total_jobs > 0 else 0
            },
            "rankings": rankings,
            "owner_details": owner_memory_stats if include_details else {},
            "insights": {
                "top_memory_user": rankings[0]['owner'] if rankings else None,
                "most_efficient_user": min(owner_memory_stats.items(), key=lambda x: abs(x[1]['memory_efficiency_percent'] - 100))[0] if owner_memory_stats else None,
                "least_efficient_user": min(owner_memory_stats.items(), key=lambda x: x[1]['memory_efficiency_percent'])[0] if owner_memory_stats else None,
                "highest_waste_user": max(owner_memory_stats.items(), key=lambda x: x[1]['memory_waste_mb'])[0] if owner_memory_stats else None
            }
        }
        
        # Add recommendations
        recommendations = []
        if overall_efficiency < 70:
            recommendations.append("Overall memory efficiency is low - consider reviewing job memory requirements")
        if overall_memory_waste > total_requested_memory * 0.3:
            recommendations.append("Significant memory waste detected - optimize job memory allocations")
        
        for owner, stats in owner_memory_stats.items():
            if stats['memory_efficiency_percent'] < 50:
                recommendations.append(f"Owner '{owner}' has very low efficiency ({stats['memory_efficiency_percent']:.1f}%) - review memory allocations")
            elif stats['memory_efficiency_percent'] > 120:
                recommendations.append(f"Owner '{owner}' may be under-allocating memory ({stats['memory_efficiency_percent']:.1f}%) - risk of job failures")
        
        analysis["recommendations"] = recommendations
        
        result = {
            "success": True,
            "time_range": time_range,
            "include_efficiency": include_efficiency,
            "include_details": include_details,
            "analysis": analysis
        }
        
        log_tool_call(session_id, user_id, "analyze_memory_usage_by_owner", 
                     {"time_range": time_range, "include_efficiency": include_efficiency, "include_details": include_details}, result)
        return result
        
    except Exception as e:
        result = {"success": False, "message": f"Error analyzing memory usage by owner: {str(e)}"}
        log_tool_call(session_id, user_id, "analyze_memory_usage_by_owner", 
                     {"time_range": time_range, "include_efficiency": include_efficiency, "include_details": include_details}, result)
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
    "continue_specific_session": FunctionTool(func=continue_specific_session),
    "start_fresh_session": FunctionTool(func=start_fresh_session),
    "get_session_history": FunctionTool(func=get_session_history),
    "get_session_summary": FunctionTool(func=get_session_summary),
    "get_user_conversation_memory": FunctionTool(func=get_user_conversation_memory),
    
    # Reporting and Analytics
    "generate_job_report": FunctionTool(func=generate_job_report),
    "generate_advanced_job_report": FunctionTool(func=generate_advanced_job_report),
    "generate_queue_wait_time_histogram": FunctionTool(func=generate_queue_wait_time_histogram),
    "get_utilization_stats": FunctionTool(func=get_utilization_stats),
    "export_job_data": FunctionTool(func=export_job_data),
    
    # HTCondor DataFrame Tools
    "get_dataframe_status": FunctionTool(func=get_dataframe_status_tool),
    "refresh_dataframe": FunctionTool(func=refresh_dataframe_tool),
    
    # Memory Analysis Tools
    "analyze_memory_usage_by_owner": FunctionTool(func=analyze_memory_usage_by_owner),
}


@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    logging.debug("Received list_tools request.")
    schemas = []
    for name, inst in ADK_AF_TOOLS.items():
        try:
            inst.name = name  # Always set the name to the dictionary key
            logging.debug(f"Converting tool schema for: {name}")
            schema = adk_to_mcp_tool_type(inst)
            schemas.append(schema)
            logging.debug(f"Successfully converted tool schema for: {name}")
        except Exception as e:
            logging.error(f"Error converting tool schema for '{name}': {e}", exc_info=True)
            # Skip this tool if it fails to convert
            continue
    return schemas


@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    logging.debug(f"Calling tool: {name}")
    
    # Create a copy of arguments to avoid modifying the original
    tool_args = arguments.copy()
    
    # Extract session context from arguments if present (but don't remove required parameters)
    # Note: If no session_id is provided, the tool functions will automatically create one
    session_id = tool_args.get('session_id', None)
    tool_context = {'session_id': session_id} if session_id else None
    
    logging.debug(f"Session ID: {session_id}")
    
    if name in ADK_AF_TOOLS:
        inst = ADK_AF_TOOLS[name]
        try:
            # Add tool_context to arguments
            if tool_context:
                tool_args['tool_context'] = tool_context
            
            resp = await inst.run_async(args=tool_args, tool_context=tool_context)
            logging.debug(f"Tool '{name}' completed successfully.")
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