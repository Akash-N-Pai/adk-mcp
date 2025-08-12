#!/usr/bin/env python3
"""
Verification script for queue wait time histogram tool
"""

import htcondor
import datetime
from collections import defaultdict

def verify_histogram_manual():
    """Manually calculate wait times and compare with tool output"""
    
    print("=== Manual Verification of Queue Wait Time Histogram ===\n")
    
    # Get jobs from last 7 days
    cutoff_time = datetime.datetime.now() - datetime.timedelta(days=7)
    constraint = f'QDate > {int(cutoff_time.timestamp())}'
    
    schedd = htcondor.Schedd()
    attrs = ["ClusterId", "ProcId", "JobStatus", "Owner", "QDate", "JobStartDate", "JobCurrentStartDate"]
    jobs = schedd.query(constraint, projection=attrs)
    
    print(f"Total jobs found: {len(jobs)}")
    print(f"Time range: Last 7 days (since {cutoff_time.isoformat()})\n")
    
    # Calculate wait times manually
    wait_times = []
    job_details = []
    
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
        
        q_date = job_info.get("qdate")
        job_start_date = job_info.get("jobstartdate")
        job_current_start_date = job_info.get("jobcurrentstartdate")
        
        # Use current start date if available, otherwise use first start date
        start_date = job_current_start_date or job_start_date
        
        if q_date and start_date and start_date > q_date:
            wait_time = start_date - q_date
            wait_times.append(wait_time)
            
            job_details.append({
                "cluster_id": job_info.get("clusterid"),
                "proc_id": job_info.get("procid"),
                "owner": job_info.get("owner"),
                "status": job_info.get("jobstatus"),
                "queue_date": datetime.datetime.fromtimestamp(q_date).isoformat(),
                "start_date": datetime.datetime.fromtimestamp(start_date).isoformat(),
                "wait_time_seconds": wait_time,
                "wait_time_minutes": wait_time / 60,
                "wait_time_hours": wait_time / 3600
            })
    
    if not wait_times:
        print("No jobs with valid wait time data found!")
        return
    
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
    
    print("=== MANUAL CALCULATION RESULTS ===")
    print(f"Jobs with wait times: {total_jobs}")
    print(f"Min wait time: {min_wait} seconds ({min_wait/60:.1f} minutes)")
    print(f"Max wait time: {max_wait} seconds ({max_wait/3600:.1f} hours)")
    print(f"Average wait time: {avg_wait:.1f} seconds ({avg_wait/60:.1f} minutes)")
    print(f"Median wait time: {median_wait:.1f} seconds ({median_wait/60:.1f} minutes)")
    print(f"25th percentile: {p25:.1f} seconds ({p25/60:.1f} minutes)")
    print(f"75th percentile: {p75:.1f} seconds ({p75/60:.1f} minutes)")
    print(f"90th percentile: {p90:.1f} seconds ({p90/60:.1f} minutes)")
    print(f"95th percentile: {p95:.1f} seconds ({p95/60:.1f} minutes)")
    print(f"99th percentile: {p99:.1f} seconds ({p99/60:.1f} minutes)")
    
    # Create simple histogram
    print("\n=== SIMPLE HISTOGRAM ===")
    bin_edges = [0, 60, 300, 900, 1800, 3600, 7200, float('inf')]  # 0, 1min, 5min, 15min, 30min, 1h, 2h, inf
    bin_labels = ["0-1min", "1-5min", "5-15min", "15-30min", "30min-1h", "1-2h", "2h+"]
    
    histogram = defaultdict(int)
    for wait_time in wait_times:
        for i, edge in enumerate(bin_edges[:-1]):
            if wait_time >= edge and wait_time < bin_edges[i+1]:
                histogram[bin_labels[i]] += 1
                break
    
    for label in bin_labels:
        count = histogram[label]
        percentage = (count / total_jobs) * 100
        print(f"{label}: {count} jobs ({percentage:.1f}%)")
    
    # Show sample jobs
    print(f"\n=== SAMPLE JOBS (first 10) ===")
    for i, job in enumerate(job_details[:10]):
        print(f"Job {job['cluster_id']}.{job['proc_id']} ({job['owner']}): "
              f"Queue: {job['queue_date']}, Start: {job['start_date']}, "
              f"Wait: {job['wait_time_minutes']:.1f} minutes")

def verify_with_condor_commands():
    """Show condor commands for verification"""
    
    print("=== CONFIRMATION COMMANDS ===\n")
    
    print("1. Check current queue status:")
    print("   condor_q")
    print("   condor_q -long | grep -E '(ClusterId|QDate|JobStartDate)'\n")
    
    print("2. Check job history:")
    print("   condor_history")
    print("   condor_history -since '2024-01-01'")
    print("   condor_history -format 'ClusterId: %d\\n' ClusterId -format 'QDate: %d\\n' QDate -format 'JobStartDate: %d\\n' JobStartDate\n")
    
    print("3. Check specific job details:")
    print("   condor_q -long <cluster_id>")
    print("   condor_history -long <cluster_id>\n")
    
    print("4. Verify timestamps:")
    print("   date -d @<timestamp>")
    print("   python3 -c 'import datetime; print(datetime.datetime.fromtimestamp(<timestamp>))'")

if __name__ == "__main__":
    try:
        verify_histogram_manual()
        print("\n" + "="*50)
        verify_with_condor_commands()
    except Exception as e:
        print(f"Error during verification: {e}")
        import traceback
        traceback.print_exc()
