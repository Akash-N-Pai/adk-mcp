#!/usr/bin/env python3
"""
Test script to compare histogram tool and advanced job report tool output with manual calculations
"""

import sys
import os
sys.path.append(os.path.dirname(__file__))

from server import generate_queue_wait_time_histogram, generate_advanced_job_report

def test_histogram_tool():
    """Test the histogram tool and compare with manual calculations"""
    
    print("=== Testing Queue Wait Time Histogram Tool ===\n")
    
    # Test with different parameters
    test_cases = [
        {"time_range": "7d", "bin_count": 5, "description": "Last 7 days, 5 bins"},
        {"time_range": "24h", "bin_count": 10, "description": "Last 24 hours, 10 bins"},
        {"time_range": "30d", "bin_count": 15, "description": "Last 30 days, 15 bins"},
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test Case {i}: {test_case['description']}")
        print("-" * 50)
        
        try:
            # Call the tool
            result = generate_queue_wait_time_histogram(
                time_range=test_case["time_range"],
                bin_count=test_case["bin_count"]
            )
            
            if result["success"]:
                stats = result["statistics"]
                histogram = result["histogram"]
                
                print(f"✅ Tool executed successfully")
                print(f"📊 Total jobs analyzed: {stats['total_jobs_analyzed']}")
                print(f"⏱️  Jobs with wait times: {stats['jobs_with_wait_times']}")
                print(f"📈 Average wait time: {stats['avg_wait_time_minutes']:.1f} minutes")
                print(f"📊 Median wait time: {stats['median_wait_time_minutes']:.1f} minutes")
                print(f"🔢 Number of histogram bins: {len(histogram['bins'])}")
                
                # Show first few bins
                print("\n📊 First 3 histogram bins:")
                for bin_data in histogram['bins'][:3]:
                    print(f"   Bin {bin_data['bin_number']}: "
                          f"{bin_data['range_start_minutes']:.1f}-{bin_data['range_end_minutes']:.1f} min: "
                          f"{bin_data['count']} jobs ({bin_data['percentage']:.1f}%)")
                
                # Show sample jobs
                if result.get("sample_jobs"):
                    print(f"\n📋 Sample jobs (first 3):")
                    for job in result["sample_jobs"][:3]:
                        print(f"   Job {job['cluster_id']}.{job['proc_id']}: "
                              f"{job['wait_time_minutes']:.1f} minutes wait")
                
            else:
                print(f"❌ Tool failed: {result['message']}")
                
        except Exception as e:
            print(f"❌ Exception occurred: {e}")
        
        print("\n" + "="*60 + "\n")

def test_advanced_job_report():
    """Test the advanced job report tool with different parameters"""
    
    print("=== Testing Advanced Job Report Tool ===\n")
    
    # Test with different parameters
    test_cases = [
        {
            "time_range": "7d", 
            "report_type": "summary", 
            "include_trends": False, 
            "include_predictions": False,
            "description": "Summary report, last 7 days, no trends/predictions"
        },
        {
            "time_range": "24h", 
            "report_type": "comprehensive", 
            "include_trends": True, 
            "include_predictions": False,
            "description": "Comprehensive report, last 24h, with trends"
        },
        {
            "time_range": "30d", 
            "report_type": "summary", 
            "include_trends": True, 
            "include_predictions": True,
            "description": "Summary report, last 30 days, with trends and predictions"
        },
        {
            "time_range": "7d", 
            "report_type": "minimal", 
            "include_trends": False, 
            "include_predictions": False,
            "description": "Minimal report, last 7 days"
        }
    ]
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"Test Case {i}: {test_case['description']}")
        print("-" * 60)
        
        try:
            # Call the tool
            result = generate_advanced_job_report(
                time_range=test_case["time_range"],
                report_type=test_case["report_type"],
                include_trends=test_case["include_trends"],
                include_predictions=test_case["include_predictions"]
            )
            
            if result["success"]:
                report = result["report"]
                
                print(f"✅ Tool executed successfully")
                print(f"📊 Output format: {result['output_format']}")
                
                # Check if it's a summary format
                if isinstance(report, dict) and "summary" in report:
                    summary = report["summary"]
                    print(f"📈 Total jobs: {summary.get('total_jobs', 'N/A')}")
                    print(f"📊 Success rate: {summary.get('success_rate_percent', 'N/A'):.1f}%")
                    print(f"⏱️  Total CPU time: {summary.get('total_cpu_time', 'N/A')}")
                    print(f"💾 Total memory usage: {summary.get('total_memory_usage_mb', 'N/A')} MB")
                    
                    # Check status distribution
                    status_dist = summary.get('status_distribution', {})
                    if status_dist:
                        print(f"📋 Status distribution:")
                        for status, count in status_dist.items():
                            print(f"   Status {status}: {count} jobs")
                
                # Check if it's comprehensive format
                elif isinstance(report, dict) and "report_metadata" in report:
                    metadata = report["report_metadata"]
                    summary = report["summary"]
                    
                    print(f"📅 Time range: {metadata.get('time_range', 'N/A')}")
                    print(f"📊 Total jobs: {metadata.get('total_jobs', 'N/A')}")
                    print(f"📈 Success rate: {summary.get('success_rate_percent', 'N/A'):.1f}%")
                    
                    # Check owner analysis
                    owner_analysis = report.get("owner_analysis", {})
                    if owner_analysis:
                        print(f"👥 Owner analysis (top 3):")
                        sorted_owners = sorted(owner_analysis.items(), 
                                             key=lambda x: x[1].get('total_jobs', 0), 
                                             reverse=True)[:3]
                        for owner, stats in sorted_owners:
                            print(f"   {owner}: {stats.get('total_jobs', 0)} jobs "
                                  f"({stats.get('success_rate', 0):.1f}% success)")
                    
                    # Check failure analysis
                    failure_analysis = report.get("failure_analysis", {})
                    if failure_analysis:
                        print(f"❌ Failure analysis:")
                        print(f"   Total failures: {failure_analysis.get('total_failures', 'N/A')}")
                        print(f"   Failure rate: {failure_analysis.get('failure_rate_percent', 'N/A'):.1f}%")
                    
                    # Check trends
                    trends = report.get("trends", {})
                    if trends:
                        print(f"📈 Trends:")
                        for trend_name, trend_value in trends.items():
                            print(f"   {trend_name}: {trend_value}")
                    
                    # Check predictions
                    predictions = report.get("predictions", {})
                    if predictions:
                        print(f"🔮 Predictions:")
                        for pred_name, pred_value in predictions.items():
                            print(f"   {pred_name}: {pred_value}")
                    
                    # Check performance insights
                    insights = report.get("performance_insights", [])
                    if insights:
                        print(f"💡 Performance insights:")
                        for insight in insights[:3]:  # Show first 3 insights
                            print(f"   - {insight}")
                
                # Check if it's CSV format
                elif isinstance(report, str) and report.startswith("ClusterId"):
                    lines = report.split('\n')
                    print(f"📄 CSV format with {len(lines)} lines")
                    print(f"📋 First line (headers): {lines[0]}")
                    if len(lines) > 1:
                        print(f"📋 Sample data line: {lines[1]}")
                
                else:
                    print(f"📄 Report format: {type(report)}")
                    if isinstance(report, dict):
                        print(f"📋 Report keys: {list(report.keys())}")
                
            else:
                print(f"❌ Tool failed: {result['message']}")
                
        except Exception as e:
            print(f"❌ Exception occurred: {e}")
            import traceback
            traceback.print_exc()
        
        print("\n" + "="*70 + "\n")

def test_advanced_job_report_with_filters():
    """Test advanced job report with different filters"""
    
    print("=== Testing Advanced Job Report with Filters ===\n")
    
    # Test with owner filter
    print("Test Case: Owner Filter")
    print("-" * 40)
    
    try:
        # Get current user for testing
        import getpass
        current_user = getpass.getuser()
        
        result = generate_advanced_job_report(
            time_range="7d",
            report_type="summary",
            owner=current_user,
            include_trends=False,
            include_predictions=False
        )
        
        if result["success"]:
            print(f"✅ Owner-filtered report successful")
            report = result["report"]
            
            if isinstance(report, dict) and "summary" in report:
                summary = report["summary"]
                print(f"📊 Total jobs for {current_user}: {summary.get('total_jobs', 'N/A')}")
                print(f"📈 Success rate: {summary.get('success_rate_percent', 'N/A'):.1f}%")
            
        else:
            print(f"❌ Owner-filtered report failed: {result['message']}")
            
    except Exception as e:
        print(f"❌ Exception: {e}")
    
    print("\n" + "="*70 + "\n")

def compare_with_manual():
    """Compare tool output with manual calculation for same time range"""
    
    print("=== Comparing Tool Output with Manual Calculation ===\n")
    
    # Use a short time range for quick comparison
    time_range = "24h"
    
    print(f"Testing with time range: {time_range}")
    print("-" * 40)
    
    try:
        # Get tool output
        tool_result = generate_queue_wait_time_histogram(time_range=time_range, bin_count=5)
        
        if tool_result["success"]:
            tool_stats = tool_result["statistics"]
            
            print("Tool Output:")
            print(f"  Total jobs analyzed: {tool_stats['total_jobs_analyzed']}")
            print(f"  Jobs with wait times: {tool_stats['jobs_with_wait_times']}")
            print(f"  Average wait time: {tool_stats['avg_wait_time_minutes']:.1f} minutes")
            print(f"  Median wait time: {tool_stats['median_wait_time_minutes']:.1f} minutes")
            
            # Now run manual verification
            print("\nManual Verification:")
            from verify_histogram import verify_histogram_manual
            verify_histogram_manual()
            
        else:
            print(f"Tool failed: {tool_result['message']}")
            
    except Exception as e:
        print(f"Error during comparison: {e}")

if __name__ == "__main__":
    print("HTCondor Tools Testing Suite\n")
    
    # Run histogram tool tests
    print("🔍 Testing Queue Wait Time Histogram Tool...")
    test_histogram_tool()
    
    # Run advanced job report tests
    print("📊 Testing Advanced Job Report Tool...")
    test_advanced_job_report()
    
    # Run filtered tests
    print("🔧 Testing Advanced Job Report with Filters...")
    test_advanced_job_report_with_filters()
    
    # Run comparison test
    print("⚖️  Running Manual Comparison...")
    compare_with_manual()
    
    print("\n=== Testing Complete ===")
    print("To verify results manually, run:")
    print("  python3 verify_histogram.py")
    print("\nTo check with condor commands:")
    print("  condor_q")
    print("  condor_history")
    print("\nTo test specific tools:")
    print("  python3 -c \"from server import generate_advanced_job_report; print(generate_advanced_job_report(time_range='24h', report_type='summary'))\"")
