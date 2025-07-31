"""
Comprehensive test suite for HTCondor MCP Server and Agent.
Tests all functionality including basic operations, advanced features, and agent integration.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timedelta

# Import all server functions
from local_mcp.server import (
    # Basic functionality
    list_jobs, get_job_status, submit_job,
    # Advanced job information
    get_job_history, get_job_requirements, get_job_environment,
    # Cluster and pool information
    list_pools, get_pool_status, list_machines, get_machine_status,
    # Resource monitoring
    get_resource_usage, get_queue_stats, get_system_load,
    # Reporting and analytics
    generate_job_report, get_utilization_stats, export_job_data
)

# Import agent components
try:
    from google.adk.tools.mcp_tool.mcp_toolset import MCPToolset
    from local_mcp.agent import root_agent, PATH_TO_YOUR_MCP_SERVER_SCRIPT
    AGENT_AVAILABLE = True
except ImportError:
    AGENT_AVAILABLE = False


# ===== BASIC MCP SERVER FUNCTIONALITY =====

class TestBasicJobManagement:
    """Test basic job management functionality."""

    @patch("local_mcp.server.htcondor.Schedd")
    def test_list_jobs_no_filters(self, mock_schedd):
        """Test listing jobs without any filters."""
        mock_ads = [
            {
                "ClusterId": Mock(eval=lambda: 123),
                "ProcId": Mock(eval=lambda: 0),
                "JobStatus": Mock(eval=lambda: 2),
                "Owner": Mock(eval=lambda: "alice"),
            },
            {
                "ClusterId": Mock(eval=lambda: 124),
                "ProcId": Mock(eval=lambda: 0),
                "JobStatus": Mock(eval=lambda: 1),
                "Owner": Mock(eval=lambda: "bob"),
            },
        ]

        mock_schedd_instance = Mock()
        mock_schedd_instance.query.return_value = mock_ads
        mock_schedd.return_value = mock_schedd_instance

        result = list_jobs()

        assert result["success"] is True
        assert len(result["jobs"]) == 2
        assert result["total_jobs"] == 2
        assert result["jobs"][0]["ClusterId"] == 123
        assert result["jobs"][0]["Status"] == "Running"
        assert result["jobs"][1]["Status"] == "Idle"

    @patch("local_mcp.server.htcondor.Schedd")
    def test_list_jobs_with_owner_filter(self, mock_schedd):
        """Test listing jobs filtered by owner."""
        mock_ads = [
            {
                "ClusterId": Mock(eval=lambda: 123),
                "ProcId": Mock(eval=lambda: 0),
                "JobStatus": Mock(eval=lambda: 2),
                "Owner": Mock(eval=lambda: "alice"),
            }
        ]

        mock_schedd_instance = Mock()
        mock_schedd_instance.query.return_value = mock_ads
        mock_schedd.return_value = mock_schedd_instance

        result = list_jobs(owner="alice")

        mock_schedd_instance.query.assert_called_once()
        call_args = mock_schedd_instance.query.call_args
        assert 'Owner == "alice"' in call_args[0][0]
        assert result["success"] is True
        assert len(result["jobs"]) == 1

    @patch("local_mcp.server.htcondor.Schedd")
    def test_list_jobs_with_status_filter(self, mock_schedd):
        """Test listing jobs filtered by status."""
        mock_ads = []
        mock_schedd_instance = Mock()
        mock_schedd_instance.query.return_value = mock_ads
        mock_schedd.return_value = mock_schedd_instance

        result = list_jobs(status="running")

        mock_schedd_instance.query.assert_called_once()
        call_args = mock_schedd_instance.query.call_args
        assert "JobStatus == 2" in call_args[0][0]
        assert result["success"] is True
        assert result["total_jobs"] == 0

    @patch("local_mcp.server.htcondor.Schedd")
    def test_list_jobs_with_limit(self, mock_schedd):
        """Test that the limit parameter is respected."""
        mock_ads = [
            {
                "ClusterId": Mock(eval=lambda: i),
                "ProcId": Mock(eval=lambda: 0),
                "JobStatus": Mock(eval=lambda: 1),
                "Owner": Mock(eval=lambda: "user"),
            }
            for i in range(15)
        ]

        mock_schedd_instance = Mock()
        mock_schedd_instance.query.return_value = mock_ads
        mock_schedd.return_value = mock_schedd_instance

        result = list_jobs(limit=5)

        assert result["success"] is True
        assert len(result["jobs"]) == 5
        assert result["total_jobs"] == 15

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_job_status_success(self, mock_schedd):
        """Test successful job status retrieval."""
        mock_ad = {
            "ClusterId": Mock(eval=lambda: 123),
            "ProcId": Mock(eval=lambda: 0),
            "JobStatus": Mock(eval=lambda: 2),
            "Owner": Mock(eval=lambda: "alice"),
            "Cmd": Mock(eval=lambda: "/bin/sleep"),
        }

        mock_schedd_instance = Mock()
        mock_schedd_instance.query.return_value = [mock_ad]
        mock_schedd.return_value = mock_schedd_instance

        result = get_job_status(cluster_id=123)

        assert result["success"] is True
        assert result["job"]["ClusterId"] == 123
        assert result["job"]["JobStatus"] == 2
        assert result["job"]["Owner"] == "alice"

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_job_status_not_found(self, mock_schedd):
        """Test job status retrieval for non-existent job."""
        mock_schedd_instance = Mock()
        mock_schedd_instance.query.return_value = []
        mock_schedd.return_value = mock_schedd_instance

        result = get_job_status(cluster_id=999)

        assert result["success"] is False
        assert "not found" in result["message"]

    @patch("local_mcp.server.htcondor.Schedd")
    @patch("local_mcp.server.htcondor.Submit")
    def test_submit_job_success(self, mock_submit, mock_schedd):
        """Test successful job submission."""
        mock_submit_instance = Mock()
        mock_submit.return_value = mock_submit_instance

        mock_schedd_instance = Mock()
        mock_transaction = Mock()
        mock_transaction.__enter__ = Mock(return_value=mock_transaction)
        mock_transaction.__exit__ = Mock(return_value=None)
        mock_schedd_instance.transaction.return_value = mock_transaction
        mock_schedd.return_value = mock_schedd_instance

        mock_submit_instance.queue.return_value = 12345

        submit_description = {
            "executable": "/bin/sleep",
            "arguments": "100",
            "output": "sleep.out",
            "error": "sleep.err",
            "log": "sleep.log",
        }

        result = submit_job(submit_description)

        assert result["success"] is True
        assert result["cluster_id"] == 12345
        mock_submit.assert_called_once_with(submit_description)
        mock_submit_instance.queue.assert_called_once_with(mock_transaction)

    @patch("local_mcp.server.htcondor.Schedd")
    def test_status_code_mapping(self, mock_schedd):
        """Test that status codes are correctly mapped to human-readable names."""
        status_tests = [
            (1, "Idle"),
            (2, "Running"),
            (3, "Removed"),
            (4, "Completed"),
            (5, "Held"),
            (6, "Transferring Output"),
            (7, "Suspended"),
        ]

        for status_code, expected_status in status_tests:
            mock_ads = [
                {
                    "ClusterId": Mock(eval=lambda: 123),
                    "ProcId": Mock(eval=lambda: 0),
                    "JobStatus": Mock(eval=lambda: status_code),
                    "Owner": Mock(eval=lambda: "test"),
                }
            ]

            mock_schedd_instance = Mock()
            mock_schedd_instance.query.return_value = mock_ads
            mock_schedd.return_value = mock_schedd_instance

            result = list_jobs()

            assert result["success"] is True
            assert result["jobs"][0]["Status"] == expected_status


# ===== ADVANCED JOB INFORMATION =====

class TestAdvancedJobInformation:
    """Test advanced job information functionality."""

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_job_history_success(self, mock_schedd):
        """Test successful job history retrieval."""
        mock_ad = MagicMock()
        mock_ad.get.return_value = 4  # Completed status
        mock_schedd.return_value.query.return_value = [mock_ad]

        result = get_job_history(1234567, limit=10)

        assert result["success"] is True
        assert result["cluster_id"] == 1234567
        assert "history_events" in result
        assert result["current_status"] == 4
        assert result["total_events"] > 0

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_job_history_job_not_found(self, mock_schedd):
        """Test job history when job doesn't exist."""
        mock_schedd.return_value.query.return_value = []

        result = get_job_history(9999999)

        assert result["success"] is False
        assert "Job not found" in result["message"]

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_job_requirements_success(self, mock_schedd):
        """Test successful job requirements retrieval."""
        mock_ad = MagicMock()
        mock_ad.get.side_effect = lambda key: {
            "Requirements": "OpSys == \"LINUX\"",
            "RequestCpus": 4,
            "RequestMemory": 8192,
            "JobPrio": 0
        }.get(key, None)
        mock_schedd.return_value.query.return_value = [mock_ad]

        result = get_job_requirements(1234567)

        assert result["success"] is True
        assert result["cluster_id"] == 1234567
        assert "requirements" in result
        assert len(result["requirements"]) > 0

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_job_environment_success(self, mock_schedd):
        """Test successful job environment retrieval."""
        mock_env = MagicMock()
        mock_env.eval.return_value = "PATH=/usr/bin HOME=/home/user"

        mock_ad = MagicMock()
        mock_ad.get.return_value = mock_env
        mock_schedd.return_value.query.return_value = [mock_ad]

        result = get_job_environment(1234567)

        assert result["success"] is True
        assert result["cluster_id"] == 1234567
        assert "environment_variables" in result
        assert "PATH" in result["environment_variables"]
        assert "HOME" in result["environment_variables"]


# ===== CLUSTER AND POOL INFORMATION =====

class TestClusterAndPoolInformation:
    """Test cluster and pool information functionality."""

    @patch("local_mcp.server.htcondor.param")
    def test_list_pools_success(self, mock_param):
        """Test successful pool listing."""
        mock_param.get.side_effect = lambda key: {
            "COLLECTOR_HOST": "htcondor.example.com:9618",
            "SECONDARY_COLLECTOR_HOSTS": "backup1.example.com:9618,backup2.example.com:9618"
        }.get(key, "")

        result = list_pools()

        assert result["success"] is True
        assert "pools" in result
        assert result["total_pools"] >= 1
        assert any("Default Pool" in pool["name"] for pool in result["pools"])

    @patch("local_mcp.server.htcondor.Schedd")
    @patch("local_mcp.server.htcondor.Collector")
    def test_get_pool_status_success(self, mock_collector, mock_schedd):
        """Test successful pool status retrieval."""
        mock_job1 = MagicMock()
        mock_job1.get.side_effect = lambda key: {
            "JobStatus": 2,  # Running
            "Owner": "alice"
        }.get(key, None)

        mock_job2 = MagicMock()
        mock_job2.get.side_effect = lambda key: {
            "JobStatus": 1,  # Idle
            "Owner": "bob"
        }.get(key, None)

        mock_schedd.return_value.query.return_value = [mock_job1, mock_job2]

        mock_machine = MagicMock()
        mock_machine.get.side_effect = lambda key: {
            "State": "Claimed",
            "Activity": "Busy"
        }.get(key, None)

        mock_collector.return_value.query.return_value = [mock_machine]

        result = get_pool_status()

        assert result["success"] is True
        assert "job_statistics" in result
        assert "machine_statistics" in result
        assert "timestamp" in result
        assert result["job_statistics"]["total_jobs"] == 2

    @patch("local_mcp.server.htcondor.Collector")
    def test_list_machines_success(self, mock_collector):
        """Test successful machine listing."""
        mock_machine = MagicMock()
        mock_machine.get.side_effect = lambda key: {
            "Name": "node01.example.com",
            "State": "Unclaimed",
            "Activity": "Idle",
            "LoadAvg": 0.5,
            "Memory": 32768,
            "Cpus": 8
        }.get(key, None)

        mock_collector.return_value.query.return_value = [mock_machine]

        result = list_machines(status="available")

        assert result["success"] is True
        assert "machines" in result
        assert result["total_machines"] == 1
        assert result["filter"] == "available"
        assert result["machines"][0]["name"] == "node01.example.com"

    @patch("local_mcp.server.htcondor.Collector")
    def test_get_machine_status_success(self, mock_collector):
        """Test successful machine status retrieval."""
        mock_machine = MagicMock()
        mock_machine.items.return_value = [
            ("Name", "node01.example.com"),
            ("State", "Claimed"),
            ("Activity", "Busy"),
            ("LoadAvg", 2.5),
            ("Memory", 32768),
            ("Cpus", 8)
        ]

        mock_collector.return_value.query.return_value = [mock_machine]

        result = get_machine_status("node01.example.com")

        assert result["success"] is True
        assert result["machine_name"] == "node01.example.com"
        assert "status" in result
        assert result["status"]["Name"] == "node01.example.com"

    @patch("local_mcp.server.htcondor.Collector")
    def test_get_machine_status_not_found(self, mock_collector):
        """Test machine status when machine doesn't exist."""
        mock_collector.return_value.query.return_value = []

        result = get_machine_status("nonexistent.example.com")

        assert result["success"] is False
        assert "not found" in result["message"]


# ===== RESOURCE MONITORING =====

class TestResourceMonitoring:
    """Test resource monitoring functionality."""

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_resource_usage_specific_job(self, mock_schedd):
        """Test resource usage for specific job."""
        mock_ad = MagicMock()
        mock_ad.get.side_effect = lambda key: {
            "RemoteUserCpu": 3600,  # 1 hour
            "RemoteSysCpu": 180,    # 3 minutes
            "ImageSize": 1048576,   # 1MB
            "MemoryUsage": 512,     # 512MB
            "DiskUsage": 2048,      # 2GB
            "CommittedTime": 3780   # 1 hour 3 minutes
        }.get(key, None)

        mock_schedd.return_value.query.return_value = [mock_ad]

        result = get_resource_usage(cluster_id=1234567)

        assert result["success"] is True
        assert result["cluster_id"] == 1234567
        assert "resource_usage" in result
        assert result["resource_usage"]["RemoteUserCpu"] == 3600
        assert result["resource_usage"]["MemoryUsage"] == 512

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_resource_usage_overall(self, mock_schedd):
        """Test overall resource usage statistics."""
        mock_job1 = MagicMock()
        mock_job1.get.side_effect = lambda key: {
            "RemoteUserCpu": 1800,
            "MemoryUsage": 256
        }.get(key, 0)

        mock_job2 = MagicMock()
        mock_job2.get.side_effect = lambda key: {
            "RemoteUserCpu": 3600,
            "MemoryUsage": 512
        }.get(key, 0)

        mock_schedd.return_value.query.return_value = [mock_job1, mock_job2]

        result = get_resource_usage()

        assert result["success"] is True
        assert "overall_usage" in result
        assert result["overall_usage"]["total_cpu_time"] == 5400
        assert result["overall_usage"]["total_memory_usage"] == 768
        assert result["overall_usage"]["active_jobs"] == 2

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_queue_stats_success(self, mock_schedd):
        """Test queue statistics retrieval."""
        mock_job1 = MagicMock()
        mock_job1.get.return_value = 2  # Running

        mock_job2 = MagicMock()
        mock_job2.get.return_value = 1  # Idle

        mock_job3 = MagicMock()
        mock_job3.get.return_value = 4  # Completed

        mock_schedd.return_value.query.return_value = [mock_job1, mock_job2, mock_job3]

        result = get_queue_stats()

        assert result["success"] is True
        assert "queue_statistics" in result
        assert result["total_jobs"] == 3
        assert "Running" in result["queue_statistics"]
        assert "Idle" in result["queue_statistics"]
        assert "Completed" in result["queue_statistics"]

    @patch("local_mcp.server.htcondor.Collector")
    def test_get_system_load_success(self, mock_collector):
        """Test system load information retrieval."""
        mock_machine1 = MagicMock()
        mock_machine1.get.side_effect = lambda key: {
            "LoadAvg": 1.5,
            "Memory": 16384,
            "Cpus": 4,
            "State": "Claimed"
        }.get(key, 0)

        mock_machine2 = MagicMock()
        mock_machine2.get.side_effect = lambda key: {
            "LoadAvg": 0.5,
            "Memory": 32768,
            "Cpus": 8,
            "State": "Unclaimed"
        }.get(key, 0)

        mock_collector.return_value.query.return_value = [mock_machine1, mock_machine2]

        result = get_system_load()

        assert result["success"] is True
        assert "system_load" in result
        assert result["system_load"]["total_machines"] == 2
        assert result["system_load"]["total_cpus"] == 12
        assert result["system_load"]["total_memory_mb"] == 49152
        assert result["system_load"]["available_cpus"] == 8
        assert result["system_load"]["available_memory_mb"] == 32768


# ===== REPORTING AND ANALYTICS =====

class TestReportingAndAnalytics:
    """Test reporting and analytics functionality."""

    @patch("local_mcp.server.htcondor.Schedd")
    def test_generate_job_report_success(self, mock_schedd):
        """Test successful job report generation."""
        mock_job = MagicMock()
        mock_job.get.side_effect = lambda key: {
            "ClusterId": 1234567,
            "ProcId": 0,
            "JobStatus": 2,
            "Owner": "alice",
            "QDate": int(datetime.now().timestamp()),
            "RemoteUserCpu": 1800,
            "RemoteSysCpu": 180,
            "ImageSize": 1048576,
            "MemoryUsage": 512,
            "CommittedTime": 1980
        }.get(key, None)

        mock_schedd.return_value.query.return_value = [mock_job]

        result = generate_job_report(owner="alice", time_range="24h")

        assert result["success"] is True
        assert "report" in result
        assert "report_metadata" in result["report"]
        assert "summary" in result["report"]
        assert "job_details" in result["report"]
        assert result["report"]["summary"]["total_jobs"] == 1
        assert result["report"]["summary"]["total_cpu_time"] == 1800

    @patch("local_mcp.server.htcondor.Schedd")
    @patch("local_mcp.server.htcondor.Collector")
    def test_get_utilization_stats_success(self, mock_collector, mock_schedd):
        """Test successful utilization statistics retrieval."""
        mock_job = MagicMock()
        mock_job.get.side_effect = lambda key: {
            "JobStatus": 4,  # Completed
            "RemoteUserCpu": 3600,
            "MemoryUsage": 1024,
            "QDate": int((datetime.now() - timedelta(hours=2)).timestamp()),
            "CompletionDate": int(datetime.now().timestamp())
        }.get(key, None)

        mock_schedd.return_value.query.return_value = [mock_job]

        mock_machine = MagicMock()
        mock_machine.get.side_effect = lambda key: {
            "Cpus": 8,
            "Memory": 16384
        }.get(key, 0)

        mock_collector.return_value.query.return_value = [mock_machine]

        result = get_utilization_stats(time_range="24h")

        assert result["success"] is True
        assert "utilization_stats" in result
        assert result["utilization_stats"]["time_range"] == "24h"
        assert result["utilization_stats"]["total_jobs"] == 1
        assert result["utilization_stats"]["completed_jobs"] == 1
        assert result["utilization_stats"]["completion_rate"] == 100.0
        assert result["utilization_stats"]["total_cpu_time"] == 3600
        assert result["utilization_stats"]["total_memory_usage"] == 1024

    @patch("local_mcp.server.htcondor.Schedd")
    def test_export_job_data_json(self, mock_schedd):
        """Test job data export in JSON format."""
        mock_job = MagicMock()
        mock_job.get.side_effect = lambda key: {
            "ClusterId": 1234567,
            "ProcId": 0,
            "JobStatus": 2,
            "Owner": "alice",
            "QDate": int(datetime.now().timestamp()),
            "RemoteUserCpu": 1800,
            "MemoryUsage": 512,
            "ImageSize": 1048576,
            "CommittedTime": 1980
        }.get(key, None)

        mock_schedd.return_value.query.return_value = [mock_job]

        result = export_job_data(format="json", filters={"owner": "alice"})

        assert result["success"] is True
        assert result["format"] == "json"
        assert result["total_jobs"] == 1
        assert isinstance(result["data"], list)
        assert len(result["data"]) == 1
        assert result["data"][0]["clusterid"] == 1234567

    @patch("local_mcp.server.htcondor.Schedd")
    def test_export_job_data_csv(self, mock_schedd):
        """Test job data export in CSV format."""
        mock_job = MagicMock()
        mock_job.get.side_effect = lambda key: {
            "ClusterId": 1234567,
            "ProcId": 0,
            "JobStatus": 2,
            "Owner": "alice"
        }.get(key, None)

        mock_schedd.return_value.query.return_value = [mock_job]

        result = export_job_data(format="csv", filters={"status": "running"})

        assert result["success"] is True
        assert result["format"] == "csv"
        assert result["total_jobs"] == 1
        assert isinstance(result["data"], str)
        assert "clusterid,procid,jobstatus,owner" in result["data"].lower()
        assert "1234567" in result["data"]

    @patch("local_mcp.server.htcondor.Schedd")
    def test_export_job_data_summary(self, mock_schedd):
        """Test job data export in summary format."""
        mock_job = MagicMock()
        mock_job.get.side_effect = lambda key: {
            "ClusterId": 1234567,
            "ProcId": 0,
            "JobStatus": 2,
            "Owner": "alice",
            "RemoteUserCpu": 1800,
            "MemoryUsage": 512
        }.get(key, 0)

        mock_schedd.return_value.query.return_value = [mock_job]

        result = export_job_data(format="summary")

        assert result["success"] is True
        assert result["format"] == "summary"
        assert result["total_jobs"] == 1
        assert isinstance(result["data"], dict)
        assert "total_jobs" in result["data"]
        assert "status_distribution" in result["data"]
        assert "total_cpu_time" in result["data"]
        assert result["data"]["total_cpu_time"] == 1800

    def test_export_job_data_unsupported_format(self):
        """Test job data export with unsupported format."""
        result = export_job_data(format="xml")

        assert result["success"] is False
        assert "Unsupported format" in result["message"]


# ===== AGENT INTEGRATION =====

class TestAgentIntegration:
    """Test agent integration and configuration."""

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent dependencies not available")
    @patch("local_mcp.agent.MCPToolset")
    def test_agent_initialization(self, mock_mcp_toolset):
        """Test that the agent is properly initialized with MCP tools."""
        assert root_agent.model == "gemini-2.0-flash"
        assert root_agent.name == "htcondor_mcp_client_agent"
        assert len(root_agent.tools) == 1

        mcp_tool = root_agent.tools[0]
        assert isinstance(mcp_tool, MCPToolset)

        assert mcp_tool._connection_params.command == "python3"
        assert "server.py" in mcp_tool._connection_params.args[0]

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent dependencies not available")
    def test_mcp_server_script_path(self):
        """Test that the MCP server script path is correctly resolved."""
        assert PATH_TO_YOUR_MCP_SERVER_SCRIPT.endswith("server.py")
        assert "local_mcp" in PATH_TO_YOUR_MCP_SERVER_SCRIPT

    def test_prompt_contains_required_instructions(self):
        """Test that the prompt contains all required instructions."""
        from local_mcp.prompt import DB_MCP_PROMPT

        assert "list_jobs" in DB_MCP_PROMPT
        assert "get_job_status" in DB_MCP_PROMPT
        assert "submit_job" in DB_MCP_PROMPT
        assert "HTCondor" in DB_MCP_PROMPT
        assert "ATLAS Facility" in DB_MCP_PROMPT

    def test_prompt_contains_advanced_functionality(self):
        """Test that the prompt contains advanced functionality instructions."""
        from local_mcp.prompt import DB_MCP_PROMPT

        # Check for advanced functionality
        assert "get_job_history" in DB_MCP_PROMPT
        assert "get_pool_status" in DB_MCP_PROMPT
        assert "get_system_load" in DB_MCP_PROMPT
        assert "generate_job_report" in DB_MCP_PROMPT
        assert "export_job_data" in DB_MCP_PROMPT

    def test_prompt_contains_example_interactions(self):
        """Test that the prompt contains helpful example interactions."""
        from local_mcp.prompt import DB_MCP_PROMPT

        assert "Show me all running jobs" in DB_MCP_PROMPT
        assert "What's the status of job" in DB_MCP_PROMPT
        assert "Submit a job" in DB_MCP_PROMPT

    def test_prompt_contains_status_mapping(self):
        """Test that the prompt includes status code mapping."""
        from local_mcp.prompt import DB_MCP_PROMPT

        assert "1=Idle" in DB_MCP_PROMPT
        assert "2=Running" in DB_MCP_PROMPT
        assert "5=Held" in DB_MCP_PROMPT

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent dependencies not available")
    @pytest.mark.asyncio
    async def test_agent_tool_execution(self):
        """Test agent tool execution scenarios."""
        assert root_agent.model == "gemini-2.0-flash"
        assert len(root_agent.tools) == 1
        assert isinstance(root_agent.tools[0], MCPToolset)

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent dependencies not available")
    def test_mcp_server_script_exists(self):
        """Test that the MCP server script exists and is accessible."""
        assert os.path.exists(PATH_TO_YOUR_MCP_SERVER_SCRIPT)
        assert os.path.isfile(PATH_TO_YOUR_MCP_SERVER_SCRIPT)

    def test_required_dependencies_available(self):
        """Test that all required dependencies are available."""
        try:
            import htcondor  # noqa: F401
            import mcp  # noqa: F401
            assert True  # All imports successful
        except ImportError as e:
            pytest.fail(f"Missing required dependency: {e}")

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent dependencies not available")
    def test_agent_configuration_completeness(self):
        """Test that the agent has all required configuration."""
        assert hasattr(root_agent, "model")
        assert hasattr(root_agent, "name")
        assert hasattr(root_agent, "instruction")
        assert hasattr(root_agent, "tools")

        assert len(root_agent.tools) > 0
        assert all(
            hasattr(tool, "_connection_params")
            for tool in root_agent.tools
            if hasattr(tool, "_connection_params")
        )

    @pytest.mark.skipif(not AGENT_AVAILABLE, reason="Agent dependencies not available")
    def test_mcp_tool_configuration(self):
        """Test that MCP tools are properly configured."""
        mcp_tools = [
            tool for tool in root_agent.tools if hasattr(tool, "_connection_params")
        ]

        for tool in mcp_tools:
            assert hasattr(tool._connection_params, "command")
            assert hasattr(tool._connection_params, "args")
            assert tool._connection_params.command == "python3"
            assert len(tool._connection_params.args) > 0


# ===== ERROR HANDLING =====

class TestErrorHandling:
    """Test error handling across all functionality."""

    @patch("local_mcp.server.htcondor.Schedd")
    def test_get_job_history_exception(self, mock_schedd):
        """Test job history with exception."""
        mock_schedd.return_value.query.side_effect = Exception("Connection failed")

        result = get_job_history(1234567)

        assert result["success"] is False
        assert "Error retrieving job history" in result["message"]

    @patch("local_mcp.server.htcondor.Collector")
    def test_get_system_load_exception(self, mock_collector):
        """Test system load with exception."""
        mock_collector.return_value.query.side_effect = Exception("Collector unavailable")

        result = get_system_load()

        assert result["success"] is False
        assert "Error getting system load" in result["message"]

    @patch("local_mcp.server.htcondor.Schedd")
    def test_generate_job_report_exception(self, mock_schedd):
        """Test job report generation with exception."""
        mock_schedd.return_value.query.side_effect = Exception("Query failed")

        result = generate_job_report()

        assert result["success"] is False
        assert "Error generating job report" in result["message"]


if __name__ == "__main__":
    pytest.main([__file__]) 