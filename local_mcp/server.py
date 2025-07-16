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

load_dotenv()

LOG_FILE_PATH = os.path.join(os.path.dirname(__file__), "mcp_server_activity.log")
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s",
    handlers=[logging.FileHandler(LOG_FILE_PATH, mode="w")],
)

logging.info("Creating MCP Server instance for HTCondor...")
app = Server("htcondor-mcp-server")


def list_jobs(owner: Optional[str] = None, status: Optional[str] = None, limit: int = 10, tool_context=None) -> dict:
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
        return result

    return {
        "success": True, 
        "jobs": [serialize_ad(ad) for ad in ads],
        "total_jobs": total_jobs
    }


def get_job_status(cluster_id: int, tool_context=None) -> dict:
    schedd = htcondor.Schedd()
    ads = schedd.query(f"ClusterId == {cluster_id}")
    if not ads:
        return {"success": False, "message": "Job not found"}
    ad = ads[0]
    job = {}
    for k, v in ad.items():
        if hasattr(v, "eval"):
            try:
                v = v.eval()
            except Exception:
                v = None
        job[k] = v
    return {"success": True, "job": job}


def submit_job(submit_description: dict, tool_context=None) -> dict:
    schedd = htcondor.Schedd()
    submit = htcondor.Submit(submit_description)
    with schedd.transaction() as txn:
        cid = submit.queue(txn)
    return {"success": True, "cluster_id": cid}


ADK_AF_TOOLS = {
    "list_jobs": FunctionTool(func=list_jobs),
    "get_job_status": FunctionTool(func=get_job_status),
    "submit_job": FunctionTool(func=submit_job),
}


@app.list_tools()
async def list_mcp_tools() -> list[mcp_types.Tool]:
    logging.info("Received list_tools request.")
    schemas = []
    for name, inst in ADK_AF_TOOLS.items():
        if not inst.name:
            inst.name = name
        schema = adk_to_mcp_tool_type(inst)
        schemas.append(schema)
    return schemas


@app.call_tool()
async def call_mcp_tool(name: str, arguments: dict) -> list[mcp_types.TextContent]:
    logging.info(f"call_tool for '{name}' args: {arguments}")
    if name in ADK_AF_TOOLS:
        inst = ADK_AF_TOOLS[name]
        try:
            resp = await inst.run_async(args=arguments, tool_context=None)
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
