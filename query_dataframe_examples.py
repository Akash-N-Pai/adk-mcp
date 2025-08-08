#!/usr/bin/env python3
"""
Examples of how to query the HTCondor dataframe directly.
This script demonstrates all the available query methods.
"""

import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from local_mcp.dataframe_manager import dataframe_manager

def initialize_dataframe():
    """Initialize the dataframe with fresh data."""
    print("=== Initializing Dataframe ===\n")
    
    result = dataframe_manager.update_dataframe(force_update=True)
    if result["success"]:
        print(f"✅ Dataframe initialized successfully!")
        print(f"   - Jobs: {result['jobs_count']}")
        print(f"   - Machines: {result['machines_count']}")
        print(f"   - Pools: {result['pools_count']}")
        return True
    else:
        print(f"❌ Error: {result['message']}")
        return False

def example_1_basic_queries():
    """Example 1: Basic dataframe queries."""
    print("\n=== Example 1: Basic Queries ===\n")
    
    # Get dataframe information
    print("1. Getting dataframe info:")
    info = dataframe_manager.get_dataframe_info()
    if info["success"]:
        print(f"   - Jobs count: {info['jobs_count']}")
        print(f"   - Machines count: {info['machines_count']}")
        print(f"   - Available job columns: {len(info['jobs_columns'])}")
        print(f"   - Sample job columns: {info['jobs_columns'][:10]}")
    
    # Get jobs summary
    print("\n2. Getting jobs summary:")
    summary = dataframe_manager.get_jobs_summary()
    if summary["success"] and summary.get("summary"):
        s = summary["summary"]
        print(f"   - Total jobs: {s['total_jobs']}")
        print(f"   - Status distribution: {s['status_distribution']}")
        print(f"   - Top owners: {dict(list(s['owners'].items())[:5])}")

def example_2_filtered_queries():
    """Example 2: Filtered queries."""
    print("\n=== Example 2: Filtered Queries ===\n")
    
    # Get jobs for specific owner
    print("1. Jobs for specific owner:")
    owner_summary = dataframe_manager.get_jobs_summary(owner="wkosteck")
    if owner_summary["success"] and owner_summary.get("summary"):
        s = owner_summary["summary"]
        print(f"   - Jobs for wkosteck: {s['total_jobs']}")
        print(f"   - Status: {s['status_distribution']}")
    
    # Get running jobs
    print("\n2. Running jobs:")
    running_summary = dataframe_manager.get_jobs_summary(status="running")
    if running_summary["success"] and running_summary.get("summary"):
        s = running_summary["summary"]
        print(f"   - Running jobs: {s['total_jobs']}")
    
    # Get idle jobs
    print("\n3. Idle jobs:")
    idle_summary = dataframe_manager.get_jobs_summary(status="idle")
    if idle_summary["success"] and idle_summary.get("summary"):
        s = idle_summary["summary"]
        print(f"   - Idle jobs: {s['total_jobs']}")

def example_3_job_details():
    """Example 3: Getting specific job details."""
    print("\n=== Example 3: Job Details ===\n")
    
    # Search for jobs first to get some cluster IDs
    print("1. Searching for jobs to get cluster IDs:")
    search_result = dataframe_manager.search_jobs("wkosteck", limit=3)
    if search_result["success"] and search_result["count"] > 0:
        print(f"   - Found {search_result['count']} jobs")
        
        # Get details for the first job
        first_job = search_result["results"][0]
        cluster_id = first_job.get("clusterid")
        
        if cluster_id:
            print(f"\n2. Getting details for cluster {cluster_id}:")
            job_details = dataframe_manager.get_job_details(int(cluster_id))
            if job_details["success"]:
                print(f"   - Found {job_details['count']} job(s)")
                job = job_details["jobs"][0]
                print(f"   - Owner: {job.get('owner')}")
                print(f"   - Status: {job.get('jobstatus')}")
                print(f"   - CPU time: {job.get('cpu_time')}")
                print(f"   - Memory usage: {job.get('memory_usage')}")

def example_4_machine_queries():
    """Example 4: Machine-related queries."""
    print("\n=== Example 4: Machine Queries ===\n")
    
    # Get machines summary
    print("1. Machines summary:")
    machines_summary = dataframe_manager.get_machines_summary()
    if machines_summary["success"] and machines_summary.get("summary"):
        s = machines_summary["summary"]
        print(f"   - Total machines: {s['total_machines']}")
        print(f"   - State distribution: {s['state_distribution']}")
        print(f"   - Total CPUs: {s['total_cpus']}")
        print(f"   - Total memory: {s['total_memory']}")
        print(f"   - Average load: {s['average_load']}")
    
    # Get idle machines
    print("\n2. Idle machines:")
    idle_machines = dataframe_manager.get_machines_summary(status="idle")
    if idle_machines["success"] and idle_machines.get("summary"):
        s = idle_machines["summary"]
        print(f"   - Idle machines: {s['total_machines']}")

def example_5_search_queries():
    """Example 5: Search queries."""
    print("\n=== Example 5: Search Queries ===\n")
    
    # Search for specific user
    print("1. Searching for user 'wkosteck':")
    search_result = dataframe_manager.search_jobs("wkosteck", limit=5)
    if search_result["success"]:
        print(f"   - Found {search_result['count']} jobs")
        for i, job in enumerate(search_result["results"][:3]):
            print(f"   - Job {i+1}: Cluster {job.get('clusterid')}, Owner: {job.get('owner')}, Status: {job.get('jobstatus')}")
    
    # Search for specific status
    print("\n2. Searching for 'running' jobs:")
    running_search = dataframe_manager.search_jobs("running", limit=3)
    if running_search["success"]:
        print(f"   - Found {running_search['count']} jobs containing 'running'")

def example_6_utilization_stats():
    """Example 6: Utilization statistics."""
    print("\n=== Example 6: Utilization Statistics ===\n")
    
    # Get 24h utilization
    print("1. 24-hour utilization:")
    util_24h = dataframe_manager.get_utilization_stats("24h")
    if util_24h["success"] and util_24h.get("stats"):
        s = util_24h["stats"]
        print(f"   - Total jobs: {s['total_jobs']}")
        print(f"   - Completed jobs: {s['completed_jobs']}")
        print(f"   - Failed jobs: {s['failed_jobs']}")
        print(f"   - Total CPU time: {s['total_cpu_time']}")
        print(f"   - CPU efficiency: {s['cpu_efficiency']:.2%}")
    
    # Get 7-day utilization
    print("\n2. 7-day utilization:")
    util_7d = dataframe_manager.get_utilization_stats("7d")
    if util_7d["success"] and util_7d.get("stats"):
        s = util_7d["stats"]
        print(f"   - Total jobs: {s['total_jobs']}")
        print(f"   - Top owners: {dict(list(s['top_owners'].items())[:5])}")

def example_7_export_data():
    """Example 7: Exporting data."""
    print("\n=== Example 7: Exporting Data ===\n")
    
    # Export jobs as JSON
    print("1. Exporting jobs as JSON:")
    export_json = dataframe_manager.export_data(data_type="jobs", format="json", filters={"owner": "wkosteck"})
    if export_json["success"]:
        print(f"   - Exported {export_json['total_records']} jobs")
        print(f"   - First job: {export_json['data'][0] if export_json['data'] else 'No data'}")
    
    # Export jobs as summary
    print("\n2. Exporting jobs as summary:")
    export_summary = dataframe_manager.export_data(data_type="jobs", format="summary")
    if export_summary["success"]:
        print(f"   - Total records: {export_summary['total_records']}")
        print(f"   - Available columns: {export_summary['data']['columns'][:10]}")
    
    # Export machines data
    print("\n3. Exporting machines data:")
    export_machines = dataframe_manager.export_data(data_type="machines", format="summary")
    if export_machines["success"]:
        print(f"   - Total machines: {export_machines['total_records']}")
        print(f"   - Available columns: {export_machines['data']['columns'][:10]}")

def example_8_direct_dataframe_access():
    """Example 8: Direct dataframe access (advanced)."""
    print("\n=== Example 8: Direct Dataframe Access ===\n")
    
    # Access the raw dataframes directly
    print("1. Direct dataframe access:")
    print(f"   - Jobs dataframe shape: {dataframe_manager.jobs_df.shape if dataframe_manager.jobs_df is not None else 'None'}")
    print(f"   - Machines dataframe shape: {dataframe_manager.machines_df.shape if dataframe_manager.machines_df is not None else 'None'}")
    
    if dataframe_manager.jobs_df is not None and not dataframe_manager.jobs_df.empty:
        print(f"   - Jobs columns: {list(dataframe_manager.jobs_df.columns)[:10]}")
        
        # Example: Get jobs with high CPU usage
        print("\n2. Jobs with high CPU usage (>1000):")
        high_cpu_jobs = dataframe_manager.jobs_df[dataframe_manager.jobs_df['cpu_time'] > 1000]
        print(f"   - High CPU jobs: {len(high_cpu_jobs)}")
        if not high_cpu_jobs.empty:
            print(f"   - Sample: Cluster {high_cpu_jobs.iloc[0]['clusterid']}, CPU: {high_cpu_jobs.iloc[0]['cpu_time']}")
        
        # Example: Get jobs by specific owner using pandas
        print("\n3. Jobs by owner using pandas:")
        owner_jobs = dataframe_manager.jobs_df[dataframe_manager.jobs_df['owner'] == 'wkosteck']
        print(f"   - Jobs for wkosteck: {len(owner_jobs)}")
        if not owner_jobs.empty:
            print(f"   - Status distribution: {owner_jobs['jobstatus'].value_counts().to_dict()}")

def main():
    """Main function to run all examples."""
    print("=== HTCondor Dataframe Query Examples ===\n")
    
    # Initialize the dataframe
    if not initialize_dataframe():
        print("Failed to initialize dataframe. Exiting.")
        return
    
    # Run all examples
    example_1_basic_queries()
    example_2_filtered_queries()
    example_3_job_details()
    example_4_machine_queries()
    example_5_search_queries()
    example_6_utilization_stats()
    example_7_export_data()
    example_8_direct_dataframe_access()
    
    print("\n=== Summary ===")
    print("✅ All examples completed!")
    print("\nYou can now use these methods to query the dataframe:")
    print("- dataframe_manager.get_jobs_summary() - Get job statistics")
    print("- dataframe_manager.get_job_details() - Get specific job details")
    print("- dataframe_manager.get_machines_summary() - Get machine statistics")
    print("- dataframe_manager.search_jobs() - Search jobs")
    print("- dataframe_manager.get_utilization_stats() - Get utilization stats")
    print("- dataframe_manager.export_data() - Export data")
    print("- dataframe_manager.get_dataframe_info() - Get dataframe info")
    print("\nFor direct access to raw dataframes:")
    print("- dataframe_manager.jobs_df - Raw jobs dataframe")
    print("- dataframe_manager.machines_df - Raw machines dataframe")
    print("- dataframe_manager.pools_df - Raw pools dataframe")

if __name__ == "__main__":
    main()
