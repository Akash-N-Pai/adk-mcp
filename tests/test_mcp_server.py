"""
Test suite for the HTCondor MCP Server functionality.
Tests the core tools: list_jobs, get_job_status, and submit_job.
"""

import pytest
from unittest.mock import Mock, patch
from local_mcp.server import list_jobs, get_job_status, submit_job


class TestListJobs:
    """Test cases for the list_jobs function."""

    @patch("local_mcp.server.htcondor.Schedd")
    def test_list_jobs_no_filters(self, mock_schedd):
        """Test listing jobs without any filters."""
        # Mock HTCondor response
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

        # Verify the constraint was built correctly
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

        # Verify the constraint was built correctly
        mock_schedd_instance.query.assert_called_once()
        call_args = mock_schedd_instance.query.call_args
        assert "JobStatus == 2" in call_args[0][0]
        assert result["success"] is True
        assert result["total_jobs"] == 0

    @patch("local_mcp.server.htcondor.Schedd")
    def test_list_jobs_with_limit(self, mock_schedd):
        """Test that the limit parameter is respected."""
        # Create more than 10 mock jobs
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
        assert len(result["jobs"]) == 5  # Should be limited to 5
        assert result["total_jobs"] == 15  # Total should still be 15


class TestGetJobStatus:
    """Test cases for the get_job_status function."""

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


class TestSubmitJob:
    """Test cases for the submit_job function."""

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

        # Mock the queue method to return a cluster ID
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


class TestStatusCodeMapping:
    """Test cases for status code mapping functionality."""

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


if __name__ == "__main__":
    pytest.main([__file__])
