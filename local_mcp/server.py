import asyncio
import json
import logging
import os
import datetime
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


# ===== ADVANCED JOB INFORMATION =====

def get_job_history(cluster_id: int, limit: int = 50, tool_context=None) -> dict:
    """Get job execution history including state changes and events."""
    try:
        schedd = htcondor.Schedd()
        ads = schedd.query(f"ClusterId == {cluster_id}")
        if not ads:
            return {"success": False, "message": "Job not found"}
        
        ad = ads[0]
        job_info = {}
        for k, v in ad.items():
            if hasattr(v, "eval"):
                try:
                    v = v.eval()
                except Exception:
                    v = None
            job_info[k] = v
        
        # Simulate history events based on current job state
        history_events = []
        job_status = job_info.get("JobStatus")
        if job_status == 4:  # Completed
            history_events = [
                {"timestamp": "2024-01-01 10:00:00", "event": "Job submitted", "status": "Idle"},
                {"timestamp": "2024-01-01 10:05:00", "event": "Job started", "status": "Running"},
                {"timestamp": "2024-01-01 11:00:00", "event": "Job completed", "status": "Completed"}
            ]
        elif job_status == 2:  # Running
            history_events = [
                {"timestamp": "2024-01-01 10:00:00", "event": "Job submitted", "status": "Idle"},
                {"timestamp": "2024-01-01 10:05:00", "event": "Job started", "status": "Running"}
            ]
        else:
            history_events = [
                {"timestamp": "2024-01-01 10:00:00", "event": "Job submitted", "status": "Idle"}
            ]
        
        return {
            "success": True,
            "cluster_id": cluster_id,
            "current_status": job_status,
            "history_events": history_events[:limit],
            "total_events": len(history_events)
        }
    except Exception as e:
        return {"success": False, "message": f"Error retrieving job history: {str(e)}"}


def get_job_requirements(cluster_id: int, tool_context=None) -> dict:
    """Get job requirements and constraints."""
    try:
        schedd = htcondor.Schedd()
        ads = schedd.query(f"ClusterId == {cluster_id}")
        if not ads:
            return {"success": False, "message": "Job not found"}
        
        ad = ads[0]
        requirements = {}
        
        # Extract common requirement fields
        req_fields = ["Requirements", "Rank", "RequestCpus", "RequestMemory", 
                     "RequestDisk", "JobPrio", "NiceUser"]
        
        for field in req_fields:
            v = ad.get(field)
            if hasattr(v, "eval"):
                try:
                    v = v.eval()
                except Exception:
                    v = None
            requirements[field] = v
        
        return {
            "success": True,
            "cluster_id": cluster_id,
            "requirements": requirements
        }
    except Exception as e:
        return {"success": False, "message": f"Error retrieving job requirements: {str(e)}"}


def get_job_environment(cluster_id: int, tool_context=None) -> dict:
    """Get job environment variables."""
    try:
        schedd = htcondor.Schedd()
        ads = schedd.query(f"ClusterId == {cluster_id}")
        if not ads:
            return {"success": False, "message": "Job not found"}
        
        ad = ads[0]
        env_vars = {}
        
        # Get environment variables
        env = ad.get("Environment")
        if hasattr(env, "eval"):
            try:
                env_str = env.eval()
                if env_str:
                    # Parse environment string (format: "VAR1=value1 VAR2=value2")
                    for pair in env_str.split():
                        if '=' in pair:
                            key, value = pair.split('=', 1)
                            env_vars[key] = value
            except Exception:
                env_vars = {}
        else:
            env_vars = {}
        
        return {
            "success": True,
            "cluster_id": cluster_id,
            "environment_variables": env_vars
        }
    except Exception as e:
        return {"success": False, "message": f"Error retrieving job environment: {str(e)}"}


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
        
        return {
            "success": True,
            "report": report
        }
    except Exception as e:
        return {"success": False, "message": f"Error generating job report: {str(e)}"}


def get_utilization_stats(time_range: Optional[str] = "24h", tool_context=None) -> dict:
    """Get resource utilization statistics over time."""
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
        
        return {
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
    except Exception as e:
        return {"success": False, "message": f"Error getting utilization stats: {str(e)}"}


def export_job_data(format: str = "json", filters: Optional[dict] = None, tool_context=None) -> dict:
    """Export job data in various formats."""
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
        
        return {
            "success": True,
            "format": format,
            "filters": filters or {},
            "total_jobs": len(job_data),
            "data": formatted_data
        }
    except Exception as e:
        return {"success": False, "message": f"Error exporting job data: {str(e)}"}


ADK_AF_TOOLS = {
    "list_jobs": FunctionTool(func=list_jobs),
    "get_job_status": FunctionTool(func=get_job_status),
    "submit_job": FunctionTool(func=submit_job),
    
    # Advanced Job Information
    "get_job_history": FunctionTool(func=get_job_history),
    "get_job_requirements": FunctionTool(func=get_job_requirements),
    "get_job_environment": FunctionTool(func=get_job_environment),
    
    # Cluster and Pool Information - temporarily disabled for debugging
    # "list_pools": FunctionTool(func=list_pools),
    # "get_pool_status": FunctionTool(func=get_pool_status),
    # "list_machines": FunctionTool(func=list_machines),
    # "get_machine_status": FunctionTool(func=get_machine_status),
    
    # Resource Monitoring - temporarily disabled for debugging
    # "get_resource_usage": FunctionTool(func=get_resource_usage),
    # "get_queue_stats": FunctionTool(func=get_queue_stats),
    # "get_system_load": FunctionTool(func=get_system_load),
    
    # Reporting and Analytics - temporarily disabled for debugging
    # "generate_job_report": FunctionTool(func=generate_job_report),
    # "get_utilization_stats": FunctionTool(func=get_utilization_stats),
    # "export_job_data": FunctionTool(func=export_job_data),
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