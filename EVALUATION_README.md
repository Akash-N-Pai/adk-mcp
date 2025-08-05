# HTCondor Agent Evaluation Guide

This guide explains how to evaluate your HTCondor agent using the ADK (Agent Development Kit) evaluation framework.

## Overview

The evaluation framework tests your HTCondor agent against predefined test cases to ensure it:
- Uses the correct tools for different queries
- Provides appropriate responses
- Handles session management correctly
- Follows the expected conversation flow

## Files Created

1. **`htcondor_agent_evaluation.test.json`** - Evaluation test cases in ADK format
2. **`test_htcondor_agent_evaluation.py`** - Pytest test file for running evaluations
3. **`run_htcondor_evaluation.py`** - Simple script to run evaluations
4. **`test_config.json`** - Evaluation criteria configuration

## Evaluation Test Cases

The evaluation covers:

### 1. Session Management
- Initial greeting and session checking
- Starting fresh sessions
- Listing user sessions
- Continuing specific sessions

### 2. Tool Discovery
- Listing available HTCondor tools
- Tool categorization and descriptions

### 3. Job Management
- Listing running jobs
- Getting job status
- Retrieving job history
- Job filtering by status and owner

### 4. Reporting and Analytics
- Utilization statistics
- Job report generation and saving
- Data export functionality

### 5. Context-Aware Features
- Memory management
- Session history tracking
- User context summaries

## Running the Evaluation

### Method 1: Using Pytest (Recommended)

```bash
# Run all evaluation tests
pytest test_htcondor_agent_evaluation.py -v

# Run specific test
pytest test_htcondor_agent_evaluation.py::TestHTCondorAgentEvaluation::test_htcondor_agent_comprehensive_evaluation -v
```

### Method 2: Using the Simple Script

```bash
# Run evaluation using the simple script
python run_htcondor_evaluation.py
```

### Method 3: Using ADK CLI (if available)

```bash
# Run evaluation using ADK CLI
adk eval local_mcp htcondor_agent_evaluation.test.json --config_file_path=test_config.json
```

## Evaluation Criteria

The evaluation uses these criteria (defined in `test_config.json`):

- **`tool_trajectory_avg_score`**: 1.0 (100% tool usage accuracy required)
- **`response_match_score`**: 0.8 (80% response similarity required)

## Understanding Results

### Pass/Fail Criteria

- **Tool Trajectory**: Agent must use the expected tools in the correct order
- **Response Match**: Agent's final response must be similar to the expected response
- **Session Management**: Agent must handle sessions correctly

### Example Output

```
🚀 Starting HTCondor agent comprehensive evaluation...
📋 Using evaluation file: /path/to/htcondor_agent_evaluation.test.json
✅ HTCondor agent evaluation completed successfully!

🧪 Testing basic HTCondor agent functionality...
✅ Agent 'htcondor_mcp_client_agent' is properly configured

🔧 Testing HTCondor agent tools...
📦 Available tools: ['list_jobs', 'get_job_status', 'submit_job', ...]
✅ All essential HTCondor tools are available
```

## Customizing Evaluation

### Adding New Test Cases

1. Edit `htcondor_agent_evaluation.test.json`
2. Add new `eval_cases` with:
   - `eval_id`: Unique identifier
   - `user_content`: User query
   - `final_response`: Expected agent response
   - `intermediate_data`: Expected tool usage

### Modifying Evaluation Criteria

Edit `test_config.json`:
```json
{
  "criteria": {
    "tool_trajectory_avg_score": 0.9,  // 90% tool accuracy
    "response_match_score": 0.7        // 70% response similarity
  }
}
```

## Troubleshooting

### Common Issues

1. **Import Errors**: Ensure ADK is installed: `pip install google-adk`
2. **Agent Not Found**: Check that `local_mcp/__init__.py` exports `root_agent`
3. **Tool Errors**: Verify MCP server is running and accessible
4. **Session Errors**: Check database permissions for session storage

### Debug Mode

For detailed debugging, run with verbose output:
```bash
pytest test_htcondor_agent_evaluation.py -v -s --tb=long
```

## Integration with CI/CD

Add to your CI/CD pipeline:

```yaml
# Example GitHub Actions step
- name: Run Agent Evaluation
  run: |
    pip install google-adk
    pytest test_htcondor_agent_evaluation.py -v
```

## Next Steps

1. **Run the evaluation** to see how your agent performs
2. **Review results** and identify areas for improvement
3. **Update test cases** based on your specific requirements
4. **Add more scenarios** as your agent capabilities expand
5. **Integrate into CI/CD** for automated testing

## Support

If you encounter issues:
1. Check the ADK documentation
2. Verify your agent configuration
3. Review the evaluation logs
4. Test individual components separately 