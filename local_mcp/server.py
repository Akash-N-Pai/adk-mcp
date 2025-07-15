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
from typing import Optional

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


def list_jobs(owner: Optional[str] = None, status: Optional[str] = None, tool_context=None) -> dict:
    """
    List jobs in HTCondor, optionally filtered by owner or status,
    serialized fully via printJson() to avoid ExprTree issues.
    """
    schedd = htcondor.Schedd()
    constraints = []
    if owner is not None:
        constraints.append(f'Owner == "{owner}"')
    if status:
        code = {
            "running": 2, "idle": 1, "held": 5,
            "completed": 4, "removed": 3,
            "transferring_output": 6, "suspended": 7
        }.get(status.lower())
        if code is not None:
            constraints.append(f"JobStatus == {code}")
    constraint = " and ".join(constraints) if constraints else "True"

    ads = schedd.query(constraint)
    jobs = [json.loads(ad.printJson()) for ad in ads]  # Clean JSON
    
    return {"success": True, "jobs": jobs}


def get_job_status(cluster_id: int, tool_context=None) -> dict:
    """
    Retrieve a single job's full ad via printJson().
    """
    schedd = htcondor.Schedd()
    ads = schedd.query(f"ClusterId == {cluster_id}")
    if not ads:
        return {"success": False, "message": "Job not found"}
    job = json.loads(ads[0].printJson())
    return {"success": True, "job": job}


def submit_job(submit_description: dict, tool_context=None) -> dict:
    """
    Submit a new job via HTCondor and return its cluster ID.
    """
    schedd = htcondor.Schedd()
    submit = htcondor.Submit(submit_description)
    with schedd.transaction() as txn:
        cid = submit.queue(txn)
    return {"success": True, "cluster_id": cid}


# Register ADK tools
ADK_AF_TOOLS = {
    "list_jobs": FunctionTool(func=list_jobs),
    "get_job_status": FunctionTool(func=get_job_status),
    "submit_job": FunctionTool(func=submit_job),
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
