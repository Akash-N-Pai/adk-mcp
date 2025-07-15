import asyncio
import json
import logging  # Added logging
import os
# import sqlite3  # REMOVE

import mcp.server.stdio  # For running as a stdio server
from dotenv import load_dotenv

# ADK Tool Imports
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type

# MCP Server Imports
from mcp import types as mcp_types  # Use alias to avoid conflict
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
    handlers=[
        logging.FileHandler(LOG_FILE_PATH, mode="w"),
    ],
)


# --- MCP Server Setup ---
logging.info(
    "Creating MCP Server instance for HTCondor..."
)  # Changed print to logging.info
app = Server("htcondor-mcp-server")

# Wrap database utility functions as ADK FunctionTools
def list_jobs(owner: Optional[str] = None, status: Optional[str] = None, tool_context=None) -> dict:
    """List all jobs in the queue, optionally filtered by owner."""
    schedd = htcondor.Schedd()
    constraint = f'Owner == "{owner}"' if owner else "True"
    jobs = schedd.query(constraint)
    return {
        "success": True,
        "jobs": [dict(job) for job in jobs]
    }

def get_job_status(cluster_id: int) -> dict:
    """Get status/details for a specific job."""
    schedd = htcondor.Schedd()
    jobs = schedd.query(f'ClusterId == {cluster_id}')
    if not jobs:
        return {"success": False, "message": "Job not found"}
    return {"success": True, "job": dict(jobs[0])}

def submit_job(submit_description: dict) -> dict:
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
    """MCP handler to list tools this server exposes."""
    logging.info(
        "MCP Server: Received list_tools request."
    )  # Changed print to logging.info
    mcp_tools_list = []
    for tool_name, adk_tool_instance in ADK_AF_TOOLS.items():
        if not adk_tool_instance.name:
            adk_tool_instance.name = tool_name

        mcp_tool_schema = adk_to_mcp_tool_type(adk_tool_instance)
        logging.info(  # Changed print to logging.info
            f"MCP Server: Advertising tool: {mcp_tool_schema.name}, InputSchema: {mcp_tool_schema.inputSchema}"
        )
        mcp_tools_list.append(mcp_tool_schema)
    return mcp_tools_list


@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    """MCP handler to execute a tool call requested by an MCP client."""
    logging.info(
        f"MCP Server: Received call_tool request for '{name}' with args: {arguments}"
    )  # Changed print to logging.info

    if name in ADK_AF_TOOLS:
        adk_tool_instance = ADK_AF_TOOLS[name]
        try:
            adk_tool_response = await adk_tool_instance.run_async(
                args=arguments,
                tool_context=None,  # type: ignore
            )
            logging.info(  # Changed print to logging.info
                f"MCP Server: ADK tool '{name}' executed. Response: {adk_tool_response}"
            )
            response_text = json.dumps(adk_tool_response, indent=2)
            return [mcp_types.TextContent(type="text", text=response_text)]

        except Exception as e:
            logging.error(
                f"MCP Server: Error executing ADK tool '{name}': {e}", exc_info=True
            )  # Changed print to logging.error, added exc_info
            error_payload = {
                "success": False,
                "message": f"Failed to execute tool '{name}': {str(e)}",
            }
            error_text = json.dumps(error_payload)
            return [mcp_types.TextContent(type="text", text=error_text)]
    else:
        logging.warning(
            f"MCP Server: Tool '{name}' not found/exposed by this server."
        )  # Changed print to logging.warning
        error_payload = {
            "success": False,
            "message": f"Tool '{name}' not implemented by this server.",
        }
        error_text = json.dumps(error_payload)
        return [mcp_types.TextContent(type="text", text=error_text)]


# --- MCP Server Runner ---
async def run_mcp_stdio_server():
    """Runs the MCP server, listening for connections over standard input/output."""
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        logging.info(
            "MCP Stdio Server: Starting handshake with client..."
        )  # Changed print to logging.info
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=app.name,
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
        logging.info(
            "MCP Stdio Server: Run loop finished or client disconnected."
        )  # Changed print to logging.info


if __name__ == "__main__":
    logging.info(
        "Launching HTCondor MCP Server via stdio..."
    )  # Changed print to logging.info
    try:
        asyncio.run(run_mcp_stdio_server())
    except KeyboardInterrupt:
        logging.info(
            "\nMCP Server (stdio) stopped by user."
        )  # Changed print to logging.info
    except Exception as e:
        logging.critical(
            f"MCP Server (stdio) encountered an unhandled error: {e}", exc_info=True
        )  # Changed print to logging.critical, added exc_info
    finally:
        logging.info(
            "MCP Server (stdio) process exiting."
        )  # Changed print to logging.info
