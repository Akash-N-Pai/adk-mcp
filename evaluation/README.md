# HTCondor MCP Agent Evaluation Framework

This directory contains the ADK-compatible evaluation framework for testing the HTCondor MCP agent on ATLAS AF.

## 📁 Files

- **`adk_evalset.json`** - ADK-compatible evaluation set with 30+ test cases
- **`adk_evaluation.py`** - ADK evaluation runner with comprehensive functionality
- **`test_agent_integration.py`** - Integration testing script
- **`README.md`** - This documentation file

## 🎯 Evaluation Set Overview

The evaluation set covers **7 main categories** with **30+ test cases**:

### 1. Basic Job Management
- Job listing with various filters (owner, status, limits)
- Job status queries for specific jobs
- Job submission with different parameters

### 2. Advanced Job Information
- Job execution history and events
- Job requirements and constraints
- Job environment variables

### 3. Cluster and Pool Information
- Available HTCondor pools
- Overall pool status and statistics
- Execution machine listings and status

### 4. Resource Monitoring
- Resource usage for specific jobs and overall system
- Queue statistics by job status
- System load and capacity information

### 5. Reporting and Analytics
- Comprehensive job reports with time ranges
- Resource utilization statistics
- Data export in multiple formats (JSON, CSV, Summary)

### 6. Complex Queries
- System overview combining multiple tools
- User performance analysis
- Multi-tool integration scenarios

### 7. Error Handling
- Invalid parameters and edge cases
- Non-existent resources
- Ambiguous queries

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- ADK agent properly configured
- HTCondor environment (for real testing on ATLAS AF)

### Running the Evaluation

```bash
# Run the complete evaluation
python evaluation/adk_evaluation.py

# Run with custom evaluation set
python evaluation/adk_evaluation.py --evalset path/to/evalset.json

# Run with custom report output
python evaluation/adk_evaluation.py --report path/to/report.json

# Run with verbose logging
python evaluation/adk_evaluation.py --verbose
```

### Using with Makefile

```bash
# Run ADK evaluation
make adk-eval

# Run with verbose output
make adk-eval-verbose

# Test agent integration
make test-agent-integration
```

## 🔧 Available Tools

The evaluation tests these **15 MCP tools**:

### Basic Job Management
- `list_jobs(owner, status, limit)` - List jobs with filtering
- `get_job_status(cluster_id)` - Get detailed job status
- `submit_job(submit_description)` - Submit new jobs

### Advanced Job Information
- `get_job_history(cluster_id, limit)` - Job execution history
- `get_job_requirements(cluster_id)` - Job requirements/constraints
- `get_job_environment(cluster_id)` - Job environment variables

### Cluster and Pool Information
- `list_pools()` - Available HTCondor pools
- `get_pool_status()` - Overall pool statistics
- `list_machines(status)` - Execution machines
- `get_machine_status(machine_name)` - Specific machine status

### Resource Monitoring
- `get_resource_usage(cluster_id)` - Resource usage (job or overall)
- `get_queue_stats()` - Queue statistics
- `get_system_load()` - System load and capacity

### Reporting and Analytics
- `generate_job_report(owner, time_range)` - Comprehensive reports
- `get_utilization_stats(time_range)` - Utilization statistics
- `export_job_data(format, filters)` - Data export (JSON/CSV/Summary)

## 📊 Evaluation Metrics

The framework measures:

1. **Tool Usage Accuracy** (0.0 - 1.0) - Correct tool calls with proper parameters
2. **Response Quality** (0.0 - 1.0) - Expected content in responses
3. **Execution Time** - Performance measurement
4. **Overall Success Rate** - Combined score (Tool ≥ 0.8 AND Response ≥ 0.6)

## 📋 Test Case Structure

Each test case follows the ADK format:

```json
{
  "name": "Case Name",
  "description": "Case description",
  "data": [
    {
      "query": "User query",
      "expected_tool_use": [
        {
          "tool_name": "tool_name",
          "tool_input": {...}
        }
      ],
      "expected_response_substrings": ["expected text"]
    }
  ]
}
```

## 🛠️ Customization

### Adding New Test Cases
1. Edit `adk_evalset.json`
2. Add new case to `eval_cases` array
3. Follow existing format structure
4. Include realistic queries and expected tool usage

### Modifying Scoring
Edit scoring functions in `adk_evaluation.py`:
- `_calculate_tool_usage_score()` - Tool usage accuracy
- `_calculate_response_score()` - Response content quality
- Success thresholds in `_run_single_case()`

### Extending Tool Detection
Modify tool extraction functions:
- `_extract_tool_usage()` - Main tool detection
- `_extract_*_params()` - Parameter extraction for each tool

## 🔍 Debugging

### Verbose Mode
```bash
python evaluation/adk_evaluation.py --verbose
```

### Integration Testing
```bash
python evaluation/test_agent_integration.py
```

### Individual Case Testing
```python
# In adk_evaluation.py main() function:
evaluator = ADKEvaluator()
case = evaluator.evalset["eval_cases"][0]  # First case
result = await evaluator._run_single_case(case)
print(f"Result: {result}")
```

## 📚 Integration with ADK Framework

This evaluation set is fully compatible with the ADK evaluation framework:

1. **Format Compliance** - Follows ADK evaluation set JSON format
2. **Tool Usage Tracking** - Monitors actual tool calls vs expected
3. **Response Validation** - Checks response content quality
4. **Report Generation** - Produces ADK-compatible reports
5. **Agent Integration** - Supports real agent communication with fallback to mock

## 🚨 Troubleshooting

### Common Issues

1. **Import Errors** - Ensure project root is in Python path
2. **File Not Found** - Check paths to evaluation set and report files
3. **Agent Communication** - Verify agent is properly configured
4. **HTCondor Access** - Ensure HTCondor environment is available

### Environment Setup

```bash
# On ATLAS AF
module load python/3.10
source ~/miniconda3/etc/profile.d/conda.sh
conda activate adk310

# Install dependencies
pip install -r requirements.txt

# Set up environment variables
export GOOGLE_API_KEY=your_key_here

# Run evaluation
python evaluation/adk_evaluation.py
```

## 📈 Sample Results

The evaluation generates detailed JSON reports with comprehensive metrics:

```json
{
  "eval_set_info": {
    "eval_set_id": "htcondor_mcp_adk_eval_v1",
    "eval_set_name": "HTCondor MCP Agent ADK Evaluation Set",
    "version": "1.0.0"
  },
  "summary": {
    "total_cases": 30,
    "successful_cases": 25,
    "failed_cases": 5,
    "success_rate": 0.833,
    "average_tool_usage_score": 0.87,
    "average_response_score": 0.75
  },
  "results": [...]
}
```

## 📞 Support

For issues with the evaluation framework:
1. Check the logs for error messages
2. Verify your agent configuration
3. Test with individual cases first
4. Ensure HTCondor environment is properly set up

---

**Note**: This evaluation framework supports both real agent communication and mock responses for development/testing without HTCondor access. 