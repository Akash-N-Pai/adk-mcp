#!/usr/bin/env python3
"""
Comprehensive test cases for HTCondor agent functionality testing.
Updated to match actual user interaction patterns from agent.py, prompt.py, and server.py.
"""

# Comprehensive test cases for HTCondor agent - Updated for real interaction patterns
COMPREHENSIVE_TEST_CASES = [
    # Initial Setup & Session Management (Realistic first interactions)
    {
        "name": "Initial Greeting",
        "query": "hi",
        "expected_tools": ["list_user_sessions"],
        "expected_output": "sessions",
        "description": "Agent should greet user and check for existing sessions"
    },
    {
        "name": "Start Fresh Session",
        "query": "start fresh",
        "expected_tools": ["start_fresh_session"],
        "expected_output": "started",
        "description": "Agent should create a completely new session"
    },
    {
        "name": "Create New Session",
        "query": "create a new session",
        "expected_tools": ["start_fresh_session"],
        "expected_output": "started",
        "description": "Agent should create a new session when requested"
    },
    
    # Tool Discovery (Realistic tool queries)
    {
        "name": "List All Tools",
        "query": "list all tools",
        "expected_tools": ["list_htcondor_tools"],
        "expected_output": "basic job management",
        "description": "Agent should show organized tool categories"
    },
    {
        "name": "Show Available Tools",
        "query": "what tools do you have available?",
        "expected_tools": ["list_htcondor_tools"],
        "expected_output": "tools",
        "description": "Agent should list available tools"
    },
    {
        "name": "Show Tools",
        "query": "show me the tools",
        "expected_tools": ["list_htcondor_tools"],
        "expected_output": "tools",
        "description": "Agent should display available tools"
    },
    
    # Job Listing & Information (Realistic job queries)
    {
        "name": "List All Jobs",
        "query": "list all the jobs",
        "expected_tools": ["list_jobs"],
        "expected_output": "clusterid",
        "description": "Agent should list jobs in table format"
    },
    {
        "name": "Show Running Jobs",
        "query": "show me running jobs",
        "expected_tools": ["list_jobs"],
        "expected_output": "running",
        "description": "Agent should filter and show running jobs"
    },
    {
        "name": "List Jobs for User",
        "query": "show me jobs for user jareddb2",
        "expected_tools": ["list_jobs"],
        "expected_output": "jareddb2",
        "description": "Agent should filter jobs by specific user"
    },
    {
        "name": "Count Running Jobs",
        "query": "how many jobs are currently running?",
        "expected_tools": ["list_jobs"],
        "expected_output": "running",
        "description": "Agent should count and report running jobs"
    },
    {
        "name": "List Held Jobs",
        "query": "list jobs with status 'Held'",
        "expected_tools": ["list_jobs"],
        "expected_output": "held",
        "description": "Agent should filter jobs by held status"
    },
    
    # Job Status & Details (Realistic status queries)
    {
        "name": "Get Job Status",
        "query": "get job status of 6657640",
        "expected_tools": ["get_job_status"],
        "expected_output": "cluster id",
        "description": "Agent should provide detailed job status information"
    },
    {
        "name": "Check Job Status",
        "query": "what's the status of job 6562147?",
        "expected_tools": ["get_job_status"],
        "expected_output": "status",
        "description": "Agent should check status of specific job"
    },
    {
        "name": "Show Job Details",
        "query": "show me details for job 6681977",
        "expected_tools": ["get_job_status"],
        "expected_output": "details",
        "description": "Agent should show comprehensive job details"
    },
    
    # Job History & Analysis (Realistic history queries)
    {
        "name": "Get Job History",
        "query": "get job history of 6657640",
        "expected_tools": ["get_job_history"],
        "expected_output": "queue date",
        "description": "Agent should show job execution history"
    },
    {
        "name": "Show Job History",
        "query": "what's the history of job 6657640?",
        "expected_tools": ["get_job_history"],
        "expected_output": "history",
        "description": "Agent should display job history with timestamps"
    },
    {
        "name": "Check Job Submission Time",
        "query": "when was job 6681977 submitted?",
        "expected_tools": ["get_job_history"],
        "expected_output": "submitted",
        "description": "Agent should show job submission timestamp"
    },
    
    # Session Management (Realistic session queries)
    {
        "name": "List User Sessions",
        "query": "list all my sessions",
        "expected_tools": ["list_user_sessions"],
        "expected_output": "sessions",
        "description": "Agent should list all user sessions with conversation counts"
    },
    {
        "name": "Continue Last Session",
        "query": "continue my last session",
        "expected_tools": ["continue_last_session"],
        "expected_output": "session",
        "description": "Agent should continue the most recent session"
    },
    {
        "name": "Continue Specific Session",
        "query": "can we go to this session d07b6c99-ac10-4656-bb9b-24d64e35b2bc",
        "expected_tools": ["continue_specific_session", "get_session_history", "get_session_summary"],
        "expected_output": "session",
        "description": "Agent should switch to specific session and provide context"
    },
    {
        "name": "Get Session Summary",
        "query": "what did I do in session d49e2c00-8d95-4d5a-83da-63da933e2c1f?",
        "expected_tools": ["get_session_summary"],
        "expected_output": "summary",
        "description": "Agent should show summary of specific session activities"
    },
    
    # Reports & Statistics (Realistic reporting queries)
    {
        "name": "Generate Job Report",
        "query": "generate job report for jareddb2",
        "expected_tools": ["generate_job_report"],
        "expected_output": "job report",
        "description": "Agent should generate comprehensive job report"
    },
    {
        "name": "Get Utilization Stats",
        "query": "get utilization stats",
        "expected_tools": ["get_utilization_stats"],
        "expected_output": "utilization",
        "description": "Agent should show system utilization statistics"
    },
    {
        "name": "Show System Statistics",
        "query": "show me system utilization statistics",
        "expected_tools": ["get_utilization_stats"],
        "expected_output": "statistics",
        "description": "Agent should display system utilization data"
    },
    {
        "name": "Get Utilization for Time Range",
        "query": "show me utilization stats for the last 7 days",
        "expected_tools": ["get_utilization_stats"],
        "expected_output": "utilization",
        "description": "Agent should show utilization for specific time range"
    },
    
    # Memory and Context (Realistic memory queries)
    {
        "name": "Get User Memory",
        "query": "what have I been working on across all sessions?",
        "expected_tools": ["get_user_conversation_memory"],
        "expected_output": "memory",
        "description": "Agent should show cross-session memory and job references"
    },
    {
        "name": "Get User Context Summary",
        "query": "show me my context summary",
        "expected_tools": ["get_user_context_summary"],
        "expected_output": "context",
        "description": "Agent should display comprehensive user context information"
    },
    {
        "name": "Save Job Report",
        "query": "save a report for job 6657640",
        "expected_tools": ["save_job_report"],
        "expected_output": "saved",
        "description": "Agent should save job report as artifact using ADK Context"
    },
    {
        "name": "Load Saved Report",
        "query": "load my saved job report",
        "expected_tools": ["load_job_report"],
        "expected_output": "report",
        "description": "Agent should load previously saved job report"
    },
    {
        "name": "Search Job Memory",
        "query": "search my memory for job information",
        "expected_tools": ["search_job_memory"],
        "expected_output": "memory",
        "description": "Agent should search memory for job-related information"
    },
    
    # Advanced Queries (Realistic complex queries)
    {
        "name": "Find User Running Jobs",
        "query": "find all jobs owned by maclwong that are running",
        "expected_tools": ["list_jobs"],
        "expected_output": "maclwong",
        "description": "Agent should filter jobs by user and status"
    },
    {
        "name": "Export Job Data",
        "query": "export job data as CSV",
        "expected_tools": ["export_job_data"],
        "expected_output": "export",
        "description": "Agent should export job data in CSV format"
    },
    {
        "name": "Add Memory Preference",
        "query": "remember that I prefer table format",
        "expected_tools": ["add_to_memory"],
        "expected_output": "remembered",
        "description": "Agent should save user preference to memory"
    }
]

# Function to get test cases
def get_comprehensive_test_cases():
    """Return the comprehensive test cases."""
    return COMPREHENSIVE_TEST_CASES

# Function to get test cases by category
def get_test_cases_by_category():
    """Return test cases organized by category."""
    categories = {
        "session_management": COMPREHENSIVE_TEST_CASES[0:3],
        "tool_discovery": COMPREHENSIVE_TEST_CASES[3:6],
        "job_listing": COMPREHENSIVE_TEST_CASES[6:11],
        "job_status": COMPREHENSIVE_TEST_CASES[11:14],
        "job_history": COMPREHENSIVE_TEST_CASES[14:17],
        "session_operations": COMPREHENSIVE_TEST_CASES[17:21],
        "reports_statistics": COMPREHENSIVE_TEST_CASES[21:25],
        "memory_context": COMPREHENSIVE_TEST_CASES[25:30],
        "advanced_queries": COMPREHENSIVE_TEST_CASES[30:33]
    }
    return categories

# Function to get realistic conversation flow
def get_realistic_conversation_flow():
    """Return a realistic conversation flow for testing."""
    return [
        "hi",
        "start fresh",
        "list all tools",
        "show me running jobs",
        "what's the status of job 6657640?",
        "get job history of 6657640",
        "list all my sessions",
        "continue my last session",
        "generate job report for jareddb2",
        "get utilization stats",
        "what have I been working on across all sessions?",
        "save a report for job 6657640",
        "find all jobs owned by maclwong that are running"
    ]

if __name__ == "__main__":
    # Print test case summary
    print("📋 Comprehensive HTCondor Agent Test Cases (Updated)")
    print("=" * 60)
    print(f"Total test cases: {len(COMPREHENSIVE_TEST_CASES)}")
    
    categories = get_test_cases_by_category()
    for category, cases in categories.items():
        print(f"\n{category.replace('_', ' ').title()}: {len(cases)} cases")
        for case in cases:
            print(f"  - {case['name']}: {case['query']}")
    
    print(f"\n🔄 Realistic Conversation Flow:")
    flow = get_realistic_conversation_flow()
    for i, query in enumerate(flow, 1):
        print(f"  {i:2d}. {query}")
    
    print(f"\n✅ Updated test cases ready for evaluation!") 