#!/usr/bin/env python3
"""
Test script for global DataFrame functionality
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from server import (
    create_session, 
    get_dataframe_status_tool, 
    refresh_dataframe_tool,
    generate_advanced_job_report,
    generate_queue_wait_time_histogram
)

def test_global_dataframe():
    """Test the global DataFrame functionality"""
    
    print("🧪 Testing Global DataFrame Functionality")
    print("=" * 50)
    
    # Test 1: Create session (should auto-initialize DataFrame)
    print("\n1️⃣ Testing session creation with auto DataFrame initialization...")
    session_result = create_session("test_user_global", {"test": "global_dataframe"})
    print(f"Session created: {session_result['success']}")
    print(f"DataFrame initialized: {session_result.get('dataframe_initialized', False)}")
    if session_result.get('dataframe_info'):
        print(f"DataFrame info: {session_result['dataframe_info']}")
    
    # Test 2: Check DataFrame status
    print("\n2️⃣ Testing DataFrame status check...")
    status_result = get_dataframe_status_tool()
    print(f"Status check: {status_result['success']}")
    print(f"DataFrame exists: {status_result.get('dataframe_exists', False)}")
    print(f"DataFrame has data: {status_result.get('dataframe_has_data', False)}")
    if status_result.get('total_jobs'):
        print(f"Total jobs: {status_result['total_jobs']}")
    
    # Test 3: Refresh DataFrame
    print("\n3️⃣ Testing DataFrame refresh...")
    refresh_result = refresh_dataframe_tool(time_range="24h")
    print(f"Refresh: {refresh_result['success']}")
    print(f"Message: {refresh_result.get('message', 'No message')}")
    if refresh_result.get('data'):
        print(f"Refresh data: {refresh_result['data']}")
    
    # Test 4: Test advanced job report with global DataFrame
    print("\n4️⃣ Testing advanced job report with global DataFrame...")
    report_result = generate_advanced_job_report(
        time_range="7d",
        report_type="comprehensive",
        include_trends=True
    )
    print(f"Advanced report: {report_result['success']}")
    print(f"Message: {report_result.get('message', 'No message')}")
    if report_result.get('data'):
        data = report_result['data']
        print(f"Total jobs analyzed: {data.get('total_jobs_analyzed', 'N/A')}")
        print(f"Success rate: {data.get('success_rate', 'N/A')}%")
    
    # Test 5: Test queue wait time histogram with global DataFrame
    print("\n5️⃣ Testing queue wait time histogram with global DataFrame...")
    histogram_result = generate_queue_wait_time_histogram(
        time_range="7d",
        bin_count=5
    )
    print(f"Histogram: {histogram_result['success']}")
    print(f"Message: {histogram_result.get('message', 'No message')}")
    if histogram_result.get('data'):
        data = histogram_result['data']
        print(f"Total jobs analyzed: {data.get('total_jobs_analyzed', 'N/A')}")
        print(f"Jobs with wait times: {data.get('jobs_with_wait_times', 'N/A')}")
    
    print("\n✅ Global DataFrame testing completed!")
    print("\n📊 Summary:")
    print(f"- Session creation: {'✅' if session_result['success'] else '❌'}")
    print(f"- DataFrame status: {'✅' if status_result['success'] else '❌'}")
    print(f"- DataFrame refresh: {'✅' if refresh_result['success'] else '❌'}")
    print(f"- Advanced report: {'✅' if report_result['success'] else '❌'}")
    print(f"- Wait time histogram: {'✅' if histogram_result['success'] else '❌'}")

if __name__ == "__main__":
    test_global_dataframe()
