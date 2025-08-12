#!/usr/bin/env python3
"""
Verification script for advanced job report tool
"""

import htcondor
import datetime
from collections import defaultdict

def verify_advanced_report_manual():
    """Manually calculate advanced job report metrics and compare with tool output"""
    
    print("=== Manual Verification of Advanced Job Report ===\n")
    
    # Get jobs from last 7 days
    cutoff_time = datetime.datetime.now() - datetime.timedelta(days=7)
    constraint = f'QDate > {int(cutoff_time.timestamp())}'
    
    schedd = htcondor.Schedd()
    attrs = [
        "ClusterId", "ProcId", "JobStatus", "Owner", "QDate", "CompletionDate",
        "RemoteUserCpu", "RemoteSysCpu", "ImageSize", "MemoryUsage", "CommittedTime",
        "RequestCpus", "RequestMemory", "RequestDisk", "ExitCode"
    ]
    jobs = schedd.query(constraint, projection=attrs)
    
    print(f"Total jobs found: {len(jobs)}")
    print(f"Time range: Last 7 days (since {cutoff_time.isoformat()})\n")
    
    # Process job data
    job_data = []
    total_cpu = 0
    total_memory = 0
    total_disk = 0
    status_counts = defaultdict(int)
    owner_stats = defaultdict(lambda: {"jobs": 0, "cpu": 0, "memory": 0, "completed": 0, "failed": 0})
    failure_reasons = defaultdict(int)
    resource_efficiency = []
    
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
        
        # Calculate metrics
        cpu_time = job_info.get("remoteusercpu", 0) or 0
        memory_usage = job_info.get("memoryusage", 0) or 0
        disk_usage = job_info.get("imagesize", 0) or 0
        status = job_info.get("jobstatus")
        owner = job_info.get("owner", "unknown")
        exit_code = job_info.get("exitcode")
        
        total_cpu += cpu_time
        total_memory += memory_usage
        total_disk += disk_usage
        status_counts[status] += 1
        
        # Owner statistics
        owner_stats[owner]["jobs"] += 1
        owner_stats[owner]["cpu"] += cpu_time
        owner_stats[owner]["memory"] += memory_usage
        
        if status == 4:  # Completed
            owner_stats[owner]["completed"] += 1
        elif status in [3, 5, 7]:  # Removed, Held, or Suspended
            owner_stats[owner]["failed"] += 1
            if exit_code:
                failure_reasons[exit_code] += 1
        
        # Resource efficiency analysis
        requested_cpus = job_info.get("requestcpus", 1) or 1
        requested_memory = job_info.get("requestmemory", 0) or 0
        if requested_cpus > 0 and requested_memory > 0:
            cpu_efficiency = cpu_time / requested_cpus if requested_cpus > 0 else 0
            memory_efficiency = memory_usage / requested_memory if requested_memory > 0 else 0
            resource_efficiency.append({
                "cluster_id": job_info.get("clusterid"),
                "cpu_efficiency": cpu_efficiency,
                "memory_efficiency": memory_efficiency,
                "overall_efficiency": (cpu_efficiency + memory_efficiency) / 2
            })
        
        job_data.append(job_info)
    
    # Calculate statistics
    total_jobs = len(job_data)
    success_rate = (status_counts.get(4, 0) / total_jobs) * 100 if total_jobs > 0 else 0
    avg_cpu_per_job = total_cpu / total_jobs if total_jobs > 0 else 0
    avg_memory_per_job = total_memory / total_jobs if total_jobs > 0 else 0
    avg_disk_per_job = total_disk / total_jobs if total_jobs > 0 else 0
    
    print("=== MANUAL CALCULATION RESULTS ===")
    print(f"Total jobs: {total_jobs}")
    print(f"Success rate: {success_rate:.1f}%")
    print(f"Total CPU time: {total_cpu:.1f} seconds")
    print(f"Total memory usage: {total_memory:.1f} MB")
    print(f"Total disk usage: {total_disk:.1f} MB")
    print(f"Average CPU per job: {avg_cpu_per_job:.1f} seconds")
    print(f"Average memory per job: {avg_memory_per_job:.1f} MB")
    print(f"Average disk per job: {avg_disk_per_job:.1f} MB")
    
    print(f"\nStatus distribution:")
    for status, count in status_counts.items():
        percentage = (count / total_jobs) * 100 if total_jobs > 0 else 0
        print(f"  Status {status}: {count} jobs ({percentage:.1f}%)")
    
    print(f"\nOwner analysis (top 5):")
    sorted_owners = sorted(owner_stats.items(), key=lambda x: x[1]["jobs"], reverse=True)[:5]
    for owner, stats in sorted_owners:
        success_rate_owner = (stats["completed"] / stats["jobs"] * 100) if stats["jobs"] > 0 else 0
        print(f"  {owner}: {stats['jobs']} jobs, {stats['completed']} completed, "
              f"{stats['failed']} failed ({success_rate_owner:.1f}% success)")
    
    print(f"\nFailure analysis:")
    total_failures = sum(failure_reasons.values())
    failure_rate = (total_failures / total_jobs * 100) if total_jobs > 0 else 0
    print(f"  Total failures: {total_failures}")
    print(f"  Failure rate: {failure_rate:.1f}%")
    if failure_reasons:
        print(f"  Failure reasons:")
        for exit_code, count in sorted(failure_reasons.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"    Exit code {exit_code}: {count} occurrences")
    
    if resource_efficiency:
        avg_efficiency = sum(r["overall_efficiency"] for r in resource_efficiency) / len(resource_efficiency)
        print(f"\nResource efficiency:")
        print(f"  Average efficiency: {avg_efficiency:.1%}")
        high_efficiency = len([r for r in resource_efficiency if r["overall_efficiency"] > 0.8])
        medium_efficiency = len([r for r in resource_efficiency if 0.5 <= r["overall_efficiency"] <= 0.8])
        low_efficiency = len([r for r in resource_efficiency if r["overall_efficiency"] < 0.5])
        print(f"  High efficiency jobs: {high_efficiency}")
        print(f"  Medium efficiency jobs: {medium_efficiency}")
        print(f"  Low efficiency jobs: {low_efficiency}")

def verify_with_condor_commands():
    """Show condor commands for verification"""
    
    print("\n=== CONFIRMATION COMMANDS ===\n")
    
    print("1. Check current queue status:")
    print("   condor_q")
    print("   condor_q -long | grep -E '(ClusterId|JobStatus|Owner|RemoteUserCpu|MemoryUsage)'\n")
    
    print("2. Check job history:")
    print("   condor_history")
    print("   condor_history -since '2024-01-01'")
    print("   condor_history -format 'ClusterId: %d\\n' ClusterId -format 'JobStatus: %d\\n' JobStatus -format 'ExitCode: %d\\n' ExitCode\n")
    
    print("3. Check specific job details:")
    print("   condor_q -long <cluster_id>")
    print("   condor_history -long <cluster_id>\n")
    
    print("4. Check resource usage:")
    print("   condor_q -format 'ClusterId: %d\\n' ClusterId -format 'RemoteUserCpu: %.2f\\n' RemoteUserCpu -format 'MemoryUsage: %.2f\\n' MemoryUsage\n")
    
    print("5. Check failure reasons:")
    print("   condor_history -format 'ExitCode: %d\\n' ExitCode | grep -v 'undefined' | sort | uniq -c | sort -nr")

def compare_tool_vs_manual():
    """Compare tool output with manual calculation"""
    
    print("\n=== COMPARISON: Tool vs Manual ===\n")
    
    try:
        from server import generate_advanced_job_report
        
        # Get tool output
        tool_result = generate_advanced_job_report(
            time_range="7d",
            report_type="summary",
            include_trends=False,
            include_predictions=False
        )
        
        if tool_result["success"]:
            print("✅ Tool executed successfully")
            report = tool_result["report"]
            
            if isinstance(report, dict) and "summary" in report:
                summary = report["summary"]
                print(f"Tool - Total jobs: {summary.get('total_jobs', 'N/A')}")
                print(f"Tool - Success rate: {summary.get('success_rate_percent', 'N/A'):.1f}%")
                print(f"Tool - Total CPU time: {summary.get('total_cpu_time', 'N/A')}")
                print(f"Tool - Total memory usage: {summary.get('total_memory_usage_mb', 'N/A')} MB")
            else:
                print("Tool output format not recognized")
        else:
            print(f"❌ Tool failed: {tool_result['message']}")
            
    except Exception as e:
        print(f"❌ Error comparing tool vs manual: {e}")

if __name__ == "__main__":
    try:
        verify_advanced_report_manual()
        verify_with_condor_commands()
        compare_tool_vs_manual()
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
