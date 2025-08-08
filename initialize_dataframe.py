#!/usr/bin/env python3
"""
Simple script to initialize and use the HTCondor dataframe.
"""

import sys
import os

# Add the project root to the path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from local_mcp.dataframe_manager import dataframe_manager

def initialize_dataframe():
    """Initialize the dataframe with fresh HTCondor data."""
    
    print("=== Initializing HTCondor Dataframe ===\n")
    
    # Step 1: Update the dataframe with fresh data
    print("1. Updating dataframe with fresh HTCondor data...")
    result = dataframe_manager.update_dataframe(force_update=True)
    
    if result["success"]:
        print(f"✅ Successfully initialized dataframe!")
        print(f"   - Jobs: {result['jobs_count']}")
        print(f"   - Machines: {result['machines_count']}")
        print(f"   - Pools: {result['pools_count']}")
        print(f"   - Last update: {result['last_update']}")
    else:
        print(f"❌ Error: {result['message']}")
        return False
    
    # Step 2: Get basic information
    print("\n2. Getting dataframe information...")
    info = dataframe_manager.get_dataframe_info()
    if info["success"]:
        print(f"✅ Dataframe info:")
        print(f"   - Jobs count: {info['jobs_count']}")
        print(f"   - Machines count: {info['machines_count']}")
        print(f"   - Available job columns: {len(info['jobs_columns'])}")
        print(f"   - Available machine columns: {len(info['machines_columns'])}")
    
    # Step 3: Get a quick summary
    print("\n3. Getting job summary...")
    summary = dataframe_manager.get_jobs_summary()
    if summary["success"] and summary.get("summary"):
        s = summary["summary"]
        print(f"✅ Job summary:")
        print(f"   - Total jobs: {s['total_jobs']}")
        print(f"   - Status distribution: {s['status_distribution']}")
        if s.get('owners'):
            top_owners = dict(list(s['owners'].items())[:5])
            print(f"   - Top owners: {top_owners}")
    
    print("\n✅ Dataframe initialization complete!")
    print("You can now use the dataframe for analysis and queries.")
    return True

def query_dataframe_examples():
    """Show examples of how to query the dataframe."""
    
    print("\n=== Dataframe Query Examples ===\n")
    
    # Example 1: Get jobs for a specific owner
    print("1. Getting jobs for specific owner...")
    owner_summary = dataframe_manager.get_jobs_summary(owner="wkosteck")
    if owner_summary["success"] and owner_summary.get("summary"):
        s = owner_summary["summary"]
        print(f"   - Jobs for wkosteck: {s['total_jobs']}")
        print(f"   - Status: {s['status_distribution']}")
    
    # Example 2: Get running jobs
    print("\n2. Getting running jobs...")
    running_summary = dataframe_manager.get_jobs_summary(status="running")
    if running_summary["success"] and running_summary.get("summary"):
        s = running_summary["summary"]
        print(f"   - Running jobs: {s['total_jobs']}")
    
    # Example 3: Search for specific jobs
    print("\n3. Searching for jobs...")
    search_result = dataframe_manager.search_jobs("wkosteck", limit=5)
    if search_result["success"]:
        print(f"   - Found {search_result['count']} jobs matching 'wkosteck'")
    
    # Example 4: Export data
    print("\n4. Exporting data...")
    export_result = dataframe_manager.export_data(data_type="jobs", format="summary")
    if export_result["success"]:
        print(f"   - Exported job summary with {export_result['total_records']} records")

def main():
    """Main function to initialize and demonstrate dataframe usage."""
    
    # Initialize the dataframe
    if initialize_dataframe():
        # Show query examples
        query_dataframe_examples()
        
        print("\n=== Usage Instructions ===")
        print("✅ The dataframe is now initialized and ready to use!")
        print("\nYou can now:")
        print("1. Use the MCP tools in your LLM workflow")
        print("2. Query specific information without input limits")
        print("3. Export data for external analysis")
        print("4. Perform complex analysis on the comprehensive dataset")
        
        print("\nExample MCP tool calls:")
        print("- update_htcondor_dataframe() - Refresh data")
        print("- get_dataframe_jobs_summary() - Get job statistics")
        print("- search_dataframe_jobs() - Search jobs")
        print("- export_dataframe_data() - Export data")

if __name__ == "__main__":
    main()
