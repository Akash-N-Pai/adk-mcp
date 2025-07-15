import asyncio
import json
import logging
import os

import mcp.server.stdio
from dotenv import load_dotenv

# ADK Tool Imports
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

# MCP Server Imports
from mcp import types as mcp_types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

import htcondor
from typing import Optional

load_dotenv()

# --- Logging Setup ---
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "mcp_server_activity.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE_PATH, mode="w")],
)

# --- MCP Server Setup ---
logging.info("Creating MCP Server instance for HTCondor...")
app = Server("htcondor-mcp-server")

# Wrap database utility functions as ADK FunctionTools
def list_jobs(owner: Optional[str] = None, status: Optional[str] = None, tool_context=None) -> dict:
    """List all jobs in the queue, optionally filtered by owner and/or status."""
    schedd = htcondor.Schedd()
    constraint_parts = []
    if owner is not None:
        constraint_parts.append(f'Owner == "{owner}"')
    if status is not None:
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
    jobs = schedd.query(constraint)
    return {"success": True, "jobs": [dict(job) for job in jobs]}

def get_job_status(cluster_id: int, tool_context=None) -> dict:
    """Get status/details for a specific job."""
    schedd = htcondor.Schedd()
    jobs = schedd.query(f'ClusterId == {cluster_id}')
    if not jobs:
        return {"success": False, "message": "Job not found"}
    return {"success": True, "job": dict(jobs[0])}

def submit_job(submit_description: dict, tool_context=None) -> dict:
    """Submit a new job to HTCondor."""
    schedd = htcondor.Schedd()
    submit = htcondor.Submit(submit_description)
    with schedd.transaction() as txn:
        cluster_id = submit.queue(txn)
    return {"success": True, "cluster_id": cluster_id}

ADK_AF_TOOLS = {
    "list_jobs": FunctionTool(func=list_jobs),
    "get_job_status": FunctionTool(func=get_job_status),
    "submit_job": FunctionTool(func=submit_job),
}

@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    logging.info("MCP Server: Received list_tools request.")
    tools = []
    for name, inst in ADK_AF_TOOLS.items():
        if not inst.name:
            inst.name = name
        schema = adk_to_mcp_tool_type(inst)
        logging.info(f"MCP Server: Advertising tool: {schema.name}, InputSchema: {schema.inputSchema}")
        tools.append(schema)
    return tools

@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    logging.info(f"MCP Server: Received call_tool request for '{name}' with args: {arguments}")
    if name in ADK_AF_TOOLS:
        inst = ADK_AF_TOOLS[name]
        try:
            resp = await inst.run_async(args=arguments, tool_context=None)
            logging.info(f"MCP Server: ADK tool '{name}' executed. Response: {resp}")
            return [mcp_types.TextContent(type="text", text=json.dumps(resp, indent=2))]
        except Exception as e:
            logging.error(f"MCP Server: Error executing ADK tool '{name}': {e}", exc_info=True)
            return [mcp_types.TextContent(type="text", text=json.dumps({"success": False, "message": str(e)}))]
    else:
        logging.warning(f"MCP Server: Tool '{name}' not found.")
        return [mcp_types.TextContent(type="text", text=json.dumps({"success": False, "message": f"Tool '{name}' not implemented."}))]

async def run_mcp_stdio_server():
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logging.info("MCP Stdio Server: Starting handshake with client...")
        await app.run(read_stream, write_stream, InitializationOptions(
            server_name=app.name,
            server_version="0.1.0",
            capabilities=app.get_capabilities(notification_options=NotificationOptions(), experimental_capabilities={}),
        ))
        logging.info("MCP Stdio Server: Run loop finished or client disconnected.")

if __name__ == "__main__":
    logging.info("Launching HTCondor MCP Server via stdio...")
    try:
        asyncio.run(run_mcp_stdio_server())
    except KeyboardInterrupt:
        logging.info("MCP Server (stdio) stopped by user.")
    except Exception as e:
        logging.critical(f"MCP Server (stdio) encountered an unhandled error: {e}", exc_info=True)
    finally:
        logging.info("MCP Server (stdio) process exiting.")
