# ADK Evaluation Framework for HTCondor MCP Agent

This directory contains the proper ADK evaluation setup for testing the HTCondor MCP agent, following the [official ADK evaluation documentation](https://google.github.io/adk-docs/evaluate/).

## 📁 Structure

```
tests/integration/
├── __init__.py
├── README.md
├── run_custom_evaluation.py          # Custom evaluation runner with detailed scoring
├── custom_evaluator.py               # Custom evaluator for trajectory and output quality
├── test_config.json                  # Evaluation criteria configuration
└── fixture/
    └── htcondor_mcp_agent/
        ├── basic_job_listing.test.json      # Individual test file
        ├── job_status_query.test.json       # Individual test file
        ├── job_submission.test.json         # Individual test file
        └── htcondor_eval_set_001.evalset.json  # Comprehensive evaluation set
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- ADK agent properly configured
- HTCondor environment (for real testing on ATLAS AF)

### Running Evaluations

#### 1. Web UI Evaluation (Recommended for Development)
```bash
# Start the ADK web UI
make adk-web

# Then navigate to http://localhost:8000 in your browser
# - Select your agent
# - Go to the "Eval" tab
# - Create test cases interactively
# - Run evaluations with custom metrics
```

#### 2. CLI Evaluation (Recommended for Automation)
```bash
# Run basic evaluation
make adk-eval

# Run with detailed results
make adk-eval-verbose

# Run with custom configuration
make adk-eval-custom
```

#### 3. Custom Evaluation (Recommended for Detailed Scoring)
```bash
# Run custom evaluation with trajectory and output quality scoring
make custom-eval
```

## 📋 Evaluation Methods

### Method 1: Individual Test Files
Each `.test.json` file contains a single session with one or more turns:

```json
{
  "sessions": [
    {
      "turns": [
        {
          "user_content": {"text": "Show me all jobs"},
          "expected_tool_use": [...],
          "expected_intermediate_agent_responses": [],
          "reference": "Expected final response..."
        }
      ],
      "session_input": {...}
    }
  ]
}
```

### Method 2: Evaluation Set File
The `.evalset.json` file contains multiple test cases in a structured format:

```json
{
  "eval_set_id": "htcondor_mcp_eval_v1",
  "eval_set_name": "HTCondor MCP Agent Evaluation Set",
  "eval_cases": [
    {
      "name": "Basic Job Listing",
      "data": [
        {
          "query": "Show me all jobs",
          "expected_tool_use": [...],
          "expected_response_substrings": [...]
        }
      ]
    }
  ]
}
```

### Method 3: Custom Evaluation
The `run_custom_evaluation.py` provides detailed scoring for:
- **Trajectory Score**: Tool usage accuracy (60% weight)
- **Output Score**: Response quality (40% weight)
- **Overall Score**: Combined assessment

## 🎯 Evaluation Criteria

The evaluation uses two main metrics:

1. **Tool Trajectory Score** (default: 1.0) - Perfect match required for tool usage
2. **Response Match Score** (default: 0.8) - 80% similarity for natural language responses

Custom criteria can be set in `test_config.json`:

```json
{
  "criteria": {
    "tool_trajectory_avg_score": 1.0,
    "response_match_score": 0.8
  }
}
```

## 🔧 Available Commands

### Makefile Commands
- `make adk-web` - Start ADK web UI for interactive evaluation
- `make adk-eval` - Run CLI evaluation
- `make adk-eval-verbose` - Run CLI evaluation with detailed results
- `make adk-eval-custom` - Run CLI evaluation with custom config
- `make custom-eval` - Run custom evaluation with detailed scoring

### Direct ADK Commands
```bash
# Web UI
adk web local_mcp/

# CLI Evaluation
adk eval local_mcp/ tests/integration/fixture/htcondor_mcp_agent/

# CLI with custom config
adk eval local_mcp/ tests/integration/fixture/htcondor_mcp_agent/ \
    --config_file_path=tests/integration/test_config.json \
    --print_detailed_results

# Custom evaluation
cd tests/integration && python run_custom_evaluation.py
```

## 📊 Test Cases

### Basic Functionality
- **Basic Job Listing** - Test `list_jobs` without filters
- **Job Status Query** - Test `get_job_status` for specific jobs
- **Job Submission** - Test `submit_job` functionality

### Advanced Functionality
- **Job History** - Test `get_job_history` retrieval
- **System Overview** - Test complex multi-tool queries
- **Filtered Queries** - Test job listing with owner filters

## 🛠️ Adding New Test Cases

### For Individual Test Files
1. Create a new `.test.json` file in `fixture/htcondor_mcp_agent/`
2. Follow the session format with turns
3. Test with `make adk-eval`

### For Evaluation Set
1. Add new cases to `htcondor_eval_set_001.evalset.json`
2. Include expected tool usage and response substrings
3. Test with `make adk-eval`

### For Custom Evaluation
1. Add new test cases to `TEST_CASES` in `run_custom_evaluation.py`
2. Include expected tools and output guidelines
3. Run with `make custom-eval`

## 🔍 Debugging

### Web UI Debugging
- Use the **Trace** tab to inspect agent execution flow
- Hover over trace rows to highlight corresponding messages
- Click trace rows for detailed inspection panels

### CLI Debugging
```bash
# Run with detailed results
make adk-eval-verbose

# Check agent structure
python -c "from local_mcp import root_agent; print('Agent available:', root_agent is not None)"
```

### Custom Evaluation Debugging
```bash
# Run with verbose output
cd tests/integration && python run_custom_evaluation.py

# Check individual test cases
python -c "from custom_evaluator import HTCondorComprehensiveEvaluator; print('Evaluator ready')"
```

## 📚 Resources

- [ADK Evaluation Documentation](https://google.github.io/adk-docs/evaluate/)
- [ADK Web UI Guide](https://google.github.io/adk-docs/evaluate/#1-adk-web---run-evaluations-via-the-web-ui)
- [ADK CLI Evaluation](https://google.github.io/adk-docs/evaluate/#3-adk-eval---run-evaluations-via-the-cli)

## 🚨 Troubleshooting

### Common Issues

1. **Import Errors** - Ensure `google-adk` is installed
2. **Agent Not Found** - Verify `root_agent` is exported from `local_mcp/__init__.py`
3. **HTCondor Connection** - Ensure HTCondor environment is available
4. **Evaluation Failures** - Check tool names match exactly in expected vs actual

### Environment Setup

```bash
# Install dependencies
make install-dev

# Verify agent structure
python -c "from local_mcp import root_agent; print('Agent available:', root_agent is not None)"

# Run basic evaluation
make adk-eval
```

---

**Note**: This evaluation framework follows the official ADK standards and provides both interactive (web UI) and automated (CLI/custom) evaluation methods for comprehensive agent testing. 