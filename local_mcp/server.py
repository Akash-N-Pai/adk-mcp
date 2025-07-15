import asyncio
import json
import logging
import os
from typing import Optional

import htcondor
import mcp.server.stdio
from dotenv import load_dotenv
from google.adk.tools.function_tool import FunctionTool
from google.adk.tools.mcp_tool.conversion_utils import adk_to_mcp_tool_type
from mcp import types as mcp_types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.models import InitializationOptions

# Load .env configs
load_dotenv()

# Setup logging
LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "mcp_server_activity.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE_PATH, mode="w")],
)

logging.info("Initializing MCP HTCondor Server...")
app = Server("htcondor-mcp-server")

# ---- TOOL: list_jobs ----
def list_jobs(owner: Optional[str] = None, status: Optional[str] = None, tool_context=None) -> dict:
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
        logging.info(f"HTCondor returned {len(ads)} jobs.")
        return {
            "success": True,
            "jobs": [json.loads(ad.printJson()) for ad in ads]
        }
    except Exception as e:
        logging.error(f"HTCondor query failed: {e}", exc_info=True)
        return {
            "success": False,
            "message": str(e)
        }



# ---- TOOL: get_job_status ----
def get_job_status(cluster_id: int, tool_context=None) -> dict:
    """Get status of a specific job by cluster ID."""
    schedd = htcondor.Schedd()
    ads = schedd.query(f"ClusterId == {cluster_id}")
    if not ads:
        return {"success": False, "message": "Job not found"}

    try:
        job = json.loads(ads[0].printJson())
        return {"success": True, "job": job}
    except Exception as e:
        logging.error(f"Failed to serialize job: {e}")
        return {"success": False, "message": f"Serialization error: {str(e)}"}


# ---- TOOL: submit_job ----
def submit_job(submit_description: dict, tool_context=None) -> dict:
    """Submit a new HTCondor job."""
    schedd = htcondor.Schedd()
    try:
        submit = htcondor.Submit(submit_description)
        with schedd.transaction() as txn:
            cluster_id = submit.queue(txn)
        return {"success": True, "cluster_id": cluster_id}
    except Exception as e:
        logging.error(f"Job submission failed: {e}")
        return {"success": False, "message": f"Submit error: {str(e)}"}


# Register tools
ADK_AF_TOOLS = {
    "list_jobs": FunctionTool(func=list_jobs),
    "get_job_status": FunctionTool(func=get_job_status),
    "submit_job": FunctionTool(func=submit_job),
}

# ---- MCP Tool Listing ----
@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    logging.info("Received list_tools request.")
    tools = []
    for name, inst in ADK_AF_TOOLS.items():
        if not inst.name:
            inst.name = name
        tools.append(adk_to_mcp_tool_type(inst))
    return tools

# ---- MCP Tool Call Handler ----
@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    logging.info(f"Tool call: {name} | Arguments: {arguments}")
    if name not in ADK_AF_TOOLS:
        return [mcp_types.TextContent(type="text", text=json.dumps({
            "success": False,
            "message": f"Tool '{name}' not registered."
        }))]

    try:
        result = await ADK_AF_TOOLS[name].run_async(args=arguments, tool_context=None)
        return [mcp_types.TextContent(type="text", text=json.dumps(result, indent=2))]
    except Exception as e:
        logging.error(f"Error running tool '{name}': {e}", exc_info=True)
        return [mcp_types.TextContent(type="text", text=json.dumps({
            "success": False,
            "message": str(e)
        }))]

# ---- MCP Server Entrypoint ----
async def run_mcp_stdio_server():
    async with mcp.server.stdio.stdio_server() as (r, w):
        logging.info("MCP stdio server starting...")
        await app.run(
            r,
            w,
            InitializationOptions(
                server_name=app.name,
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )
        logging.info("MCP stdio server stopped.")

# ---- MAIN ----
if __name__ == "__main__":
    try:
        asyncio.run(run_mcp_stdio_server())
    except KeyboardInterrupt:
        logging.info("MCP server interrupted by user.")
    except Exception as e:
        logging.critical(f"Fatal server error: {e}", exc_info=True)
    finally:
        logging.info("Server shutting down.")
