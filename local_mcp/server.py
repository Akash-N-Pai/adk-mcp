import asyncio
import json
import logging
import os

import mcp.server.stdio
from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type
from mcp import types as mcp_types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions
import htcondor
from typing import Union

# Load environment variables (e.g. HTCondor config)
load_dotenv()

# Logging setup
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "mcp_server_activity.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE_PATH, mode="w")],
)

logging.info("Initializing HTCondor MCP Server...")
app = Server("htcondor-mcp-server")

# ---- TOOL: list_jobs ----
def list_jobs(owner: Union[str, None] = None, status: Union[str, None] = None, tool_context=None) -> dict:
    """
    List jobs in HTCondor, optionally filtered by owner or status.
    Returns only the first 10 jobs, and includes total_jobs count.
    All jobs are safely serialized using printJson().
    """
    logging.info(f"HTCondor query started: owner={owner}, status={status}")
    try:
        schedd = htcondor.Schedd()
        constraint_parts = []
        if owner:
            constraint_parts.append(f'Owner == "{owner}"')
        if status:
            status_map = {
                'running': 2,
                'idle': 1,
                'held': 5,
                'completed': 4,
                'removed': 3,
                'transferring_output': 6,
                'suspended': 7
            }
            status_code = status_map.get(status.lower())
            if status_code is not None:
                constraint_parts.append(f'JobStatus == {status_code}')
        constraint = ' and '.join(constraint_parts) if constraint_parts else "True"
        ads = schedd.query(constraint)
        total_jobs = len(ads)
        # ✅ Safely serialize using printJson(), and only return first 10 jobs
        jobs = [json.loads(ad.printJson()) for ad in ads[:10]]
        return {
            "success": True,
            "jobs": jobs,
            "total_jobs": total_jobs
        }
    except Exception as e:
        logging.error(f"HTCondor query failed: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e)
        }

# ---- TOOL: get_job_status ----
def get_job_status(cluster_id: str, tool_context=None) -> dict:
    """
    Get status of a specific job by cluster.proc (e.g., '6351153.61' or just '6351153').
    Safely serializes the job ad using printJson().
    """
    schedd = htcondor.Schedd()
    try:
        if '.' in str(cluster_id):
            cluster, proc = str(cluster_id).split('.')
            query = f"ClusterId == {int(cluster)} && ProcId == {int(proc)}"
        else:
            cluster = int(cluster_id)
            query = f"ClusterId == {cluster}"
        ads = schedd.query(query)
        if not ads:
            return {"success": False, "message": "Job not found"}
        job = json.loads(ads[0].printJson())
        return {"success": True, "job": job}
    except Exception as e:
        logging.error(f"Failed to get job status: {e}")
        return {"success": False, "message": f"Error: {str(e)}"}

# ---- TOOL: submit_job ----
def submit_job(submit_description: dict, tool_context=None) -> dict:
    """
    Submit a new job via HTCondor and return its cluster ID.
    """
    try:
        schedd = htcondor.Schedd()
        submit = htcondor.Submit(submit_description)
        with schedd.transaction() as txn:
            cid = submit.queue(txn)
        return {"success": True, "cluster_id": cid}
    except Exception as e:
        logging.error(f"HTCondor submit failed: {e}", exc_info=True)
        return {"success": False, "message": str(e)}

# ---- TOOL: count_jobs ----
def count_jobs(owner: Union[str, None] = None, status: Union[str, None] = None, tool_context=None) -> dict:
    """
    Count total number of jobs in HTCondor, optionally filtered by owner or status.
    Lightweight tool that only returns the count, not job data.
    """
    logging.info(f"HTCondor count query: owner={owner}, status={status}")
    try:
        schedd = htcondor.Schedd()
        constraint_parts = []
        if owner:
            constraint_parts.append(f'Owner == "{owner}"')
        if status:
            status_map = {
                'running': 2,
                'idle': 1,
                'held': 5,
                'completed': 4,
                'removed': 3,
                'transferring_output': 6,
                'suspended': 7
            }
            status_code = status_map.get(status.lower())
            if status_code is not None:
                constraint_parts.append(f'JobStatus == {status_code}')
        constraint = ' and '.join(constraint_parts) if constraint_parts else "True"
        ads = schedd.query(constraint)
        total_count = len(ads)
        return {
            "success": True,
            "total_jobs": total_count,
            "filter": {
                "owner": owner,
                "status": status
            }
        }
    except Exception as e:
        logging.error(f"HTCondor count query failed: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e)
        }

# ---- TOOL: get_session_state ----
def get_session_state(tool_context=None) -> dict:
    """
    Get current session state information including recent jobs, job history, and active filters.
    """
    try:
        # For now, return a basic session state structure
        # In a full implementation, this would track actual session data
        session_info = {
            "recent_jobs_count": 0,
            "job_history_count": 0,
            "last_query_time": None,
            "active_filters": {},
            "recent_job_statuses": [],
            "session_id": "default_session"
        }
        return {
            "success": True,
            "session_state": session_info
        }
    except Exception as e:
        logging.error(f"Failed to get session state: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e)
        }

# Register ADK tools
ADK_AF_TOOLS = {
    "list_jobs": FunctionTool(func=list_jobs),
    "get_job_status": FunctionTool(func=get_job_status),
    "submit_job": FunctionTool(func=submit_job),
    "count_jobs": FunctionTool(func=count_jobs),
    "get_session_state": FunctionTool(func=get_session_state),
}

@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    logging.info("Responding to list_tools request")
    tools = []
    for name, inst in ADK_AF_TOOLS.items():
        if not inst.name:
            inst.name = name
        tools.append(adk_to_mcp_tool_type(inst))
    return tools

@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    logging.info(f"Received call_tool: {name} with args {arguments}")
    if name not in ADK_AF_TOOLS:
        payload = {"success": False, "message": f"Tool '{name}' not found"}
        return [mcp_types.TextContent(type="text", text=json.dumps(payload))]
    inst = ADK_AF_TOOLS[name]
    try:
        resp = await inst.run_async(args=arguments, tool_context=None)
        return [mcp_types.TextContent(type="text", text=json.dumps(resp, indent=2))]
    except Exception as e:
        logging.error(f"Error in '{name}': {e}", exc_info=True)
        payload = {"success": False, "message": str(e)}
        return [mcp_types.TextContent(type="text", text=json.dumps(payload))]

async def run_mcp_stdio_server():
    async with mcp.server.stdio.stdio_server() as (reader, writer):
        logging.info("Starting MCP stdio server...")
        await app.run(
            reader,
            writer,
            InitializationOptions(
                server_name=app.name,
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(), experimental_capabilities={}
                ),
            ),
        )
        logging.info("MCP stdio connection ended.")

if __name__ == "__main__":
    try:
        asyncio.run(run_mcp_stdio_server())
    except KeyboardInterrupt:
        logging.info("Server stopped by user.")
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}", exc_info=True)
    finally:
        logging.info("Server exiting.")
