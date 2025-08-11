# HTCondor MCP Agent for ATLAS Facility

A comprehensive Agent Development Kit (ADK) agent that provides advanced HTCondor management capabilities for the ATLAS Facility. The agent uses a local Model Context Protocol (MCP) server to interact with HTCondor, offering job management, resource monitoring, reporting, and analytics functionality with **Google ADK Context integration** for persistent session management and cross-conversation memory.

---

## 🚀 Quick Start

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Clone and setup
git clone <repository-url>
cd adk-mcp


# Set up API key
echo "GOOGLE_API_KEY=your_gemini_api_key_here" > .env

adk web
```

---

## 📁 Project Structure

```
adk-mcp/
├── local_mcp/
│   ├── agent.py               # ADK agent with session management and context
│   ├── server.py              # MCP server with 26 tools including session tools
│   ├── session_context_simple.py # Simplified 3-table SQLite session management
│   ├── prompt.py              # Comprehensive prompt with session instructions
│   ├── __init__.py
│   └── mcp_server_activity.log # Server activity log (auto-generated)
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── pytest.ini                # Pytest configuration
├── eval.py                    # Custom evaluation script
├── test_config.json           # Test configuration
├── htcondor_agent_testfile.test.json # Test cases
├── evaluated_eval_cases.json  # Evaluation results
├── .env                       # Environment variables (create this)
└── readme.md                  # Project documentation
```

---

## 🛠️ Available Tools (26 MCP Tools)

The MCP server exposes comprehensive tools for HTCondor management and session management:

### Basic Job Management
- **`list_jobs(owner, status, limit)`**: List jobs with filtering options
- **`get_job_status(cluster_id)`**: Get detailed status for specific job
- **`submit_job(submit_description)`**: Submit new jobs to HTCondor

### Advanced Job Information
- **`get_job_history(cluster_id, limit)`**: Get job execution history and events

### Cluster and Pool Information
- **`list_pools()`**: List available HTCondor pools
- **`get_pool_status()`**: Get overall pool status and statistics
- **`list_machines(status)`**: List execution machines with status filtering
- **`get_machine_status(machine_name)`**: Get detailed machine status

### Resource Monitoring
- **`get_resource_usage(cluster_id)`**: Get resource usage (specific job or overall)
- **`get_queue_stats()`**: Get queue statistics by job status
- **`get_system_load()`**: Get overall system load and capacity

### Session Management & Context
- **`list_htcondor_tools()`**: List only HTCondor job management tools
- **`list_user_sessions()`**: List all user sessions
- **`continue_last_session()`**: Continue most recent session
- **`continue_specific_session(session_id)`**: Continue specific session by ID
- **`start_fresh_session()`**: Start completely new session
- **`get_session_history(session_id)`**: Get conversation history for session
- **`get_session_summary(session_id)`**: Get summary of session activities
- **`get_user_conversation_memory()`**: Get memory across all sessions
- **`add_to_memory(key, value, global_memory)`**: Add information to memory
- **`search_job_memory(query)`**: Search memory for job information
- **`get_user_context_summary()`**: Get comprehensive user context

### Reporting and Analytics
- **`generate_job_report(owner, time_range)`**: Generate comprehensive job reports
- **`get_utilization_stats(time_range)`**: Get resource utilization statistics
- **`export_job_data(format, filters)`**: Export job data (JSON/CSV/Summary)

### Context-Aware Tools (ADK Context Integration)
- **`save_job_report(cluster_id, report_name)`**: Save job report to memory
- **`load_job_report(report_name)`**: Load saved job report from memory

All tools return structured JSON responses with success flags and relevant data.

---

## 🤖 Agent Capabilities

The agent provides intelligent HTCondor management with **Google ADK Context integration** and these capabilities:

### Job Management
- **Smart Filtering**: Filter jobs by owner, status, time ranges
- **Batch Operations**: Handle multiple jobs efficiently
- **Status Tracking**: Monitor job states and transitions
- **Resource Monitoring**: Track CPU, memory, and disk usage

### System Monitoring
- **Pool Management**: Monitor HTCondor pools and collectors
- **Machine Status**: Track execution nodes and availability
- **Resource Analytics**: Analyze system utilization and performance
- **Capacity Planning**: Understand available resources

### Reporting and Analytics
- **Comprehensive Reports**: Generate detailed job and system reports
- **Time-based Analysis**: Analyze performance over different time periods
- **Data Export**: Export data in multiple formats for external analysis
- **Utilization Metrics**: Track resource efficiency and bottlenecks

### Advanced Features
- **Job History**: Track job lifecycle and state changes
- **Requirements Analysis**: Understand job constraints and needs
- **Environment Management**: Monitor job execution environments
- **Error Handling**: Robust error handling and recovery

### Session Management & Context
- **Persistent Sessions**: Maintain session state across conversations
- **Cross-Session Memory**: Remember user preferences and job references
- **Session Continuity**: Continue previous conversations seamlessly
- **Context Awareness**: Provide personalized responses based on history
- **Simplified Database**: 3-table SQLite schema for efficient storage

---

## 📊 Example Interactions

### Basic Job Management
```
User: Show me all running jobs for user alice.
Agent: [Calls list_jobs with owner="alice", status="running"]
Output:
Jobs for user alice (Running):
| ClusterId | ProcId | Status  | Owner  |
|-----------|--------|---------|--------|
| 1234567   | 0      | Running | alice  |
| 1234568   | 0      | Running | alice  |
Total jobs shown: 2
```

### Advanced Monitoring
```
User: What's the current system load and available resources?
Agent: [Calls get_system_load]
Output:
System Load Summary:
- Total Machines: 50
- Total CPUs: 200
- Available CPUs: 45
- Total Memory: 800GB
- Available Memory: 180GB
- Utilization: 77.5%
```

### Reporting and Analytics
```
User: Generate a report for user bob's jobs from the last 7 days.
Agent: [Calls generate_job_report with owner="bob", time_range="7d"]
Output:
Job Report for user bob (Last 7 days):
- Total Jobs: 15
- Status Distribution: Running: 3, Completed: 10, Held: 2
- Total CPU Time: 45.2 hours
- Total Memory Usage: 2.1GB
- Average CPU per Job: 3.0 hours
```

### Resource Monitoring
```
User: What resources is job 1234567 using?
Agent: [Calls get_resource_usage with cluster_id=1234567]
Output:
Resource Usage for Job 1234567:
- CPU Time: 2.5 hours
- Memory Usage: 512MB
- Disk Usage: 1.2GB
- Committed Time: 3.1 hours
```

### Session Management
```
User: List all my sessions
Agent: [Calls list_user_sessions()]
Output:
Your Sessions:
| Session ID | Created | Last Activity | Conversations |
|------------|---------|---------------|---------------|
| d07b6c99... | 2025-07-31 | 2025-07-31 | 15 |

User: Continue session d07b6c99-ac10-4656-bb9b-24d64e35b2bc
Agent: [Calls continue_specific_session() and get_session_history()]
Output:
Welcome back! I can see you were working with jobs 1234567 and 1234568 earlier...
```

---

## 🧪 Testing & Evaluation

### ADK Evaluation Framework
```bash
make adk-eval               # Run ADK evaluation
make adk-eval-verbose       # Run with verbose output
make adk-eval-custom        # Run with custom paths
make custom-eval            # Run custom evaluation with detailed scoring
```

### Custom Evaluation
```bash
python eval.py              # Run custom evaluation script
```

**Evaluation Coverage:**
- **Custom Test Cases** covering comprehensive scenarios
- **26 MCP Tools** comprehensively tested including session management
- **Complex Scenarios** including multi-tool interactions
- **Error Handling** and edge cases
- **Agent Integration** testing
- **Session Management** testing

**Test Categories:**
1. Basic Job Management
2. Advanced Job Information
3. Cluster and Pool Information
4. Resource Monitoring
5. Session Management
6. Reporting and Analytics
7. Complex Queries
8. Error Handling

---

## 🛠️ Development Workflow

```bash
make format         # Format code with black
make lint           # Run linting checks (flake8, mypy)
make clean          # Remove build/test artifacts
```

---

## ⚙️ Environment Variables

- `GOOGLE_API_KEY` (required): API key for Gemini model

Create a `.env` file in the project root:
```
GOOGLE_API_KEY=your_gemini_api_key_here
```

---

## 📦 Dependencies

- **Production:** (see `requirements.txt`)
    - `google-adk==1.9.0`
    - `mcp==1.9.1`
    - `deprecated==1.2.13`
    - `htcondor==24.9.2`
    - `langchain>=0.1.0`
    - `langchain-community>=0.1.0`
    - `langsmith>=0.1.0`
    - `google-generativeai>=0.3.0`
- **Development:** (see `requirements-dev.txt`)
    - `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`
    - `black`, `flake8`, `mypy`, `pre-commit`

---

## 🐛 Troubleshooting

### Common Issues

- **`No module named 'htcondor'`**:
    - Ensure HTCondor Python bindings are installed
    - On ATLAS Facility, these are usually pre-installed
- **Agent not responding**:
    - Verify `GOOGLE_API_KEY` is set correctly
    - Check agent logs for connection issues
- **Python version issues on ATLAS**:
    - Install Python 3.10+ via Miniconda:

```bash
cd ~
wget https://repo.anaconda.com/miniconda/Miniconda3-py310_24.1.2-0-Linux-x86_64.sh -O miniconda.sh
bash miniconda.sh -b -p $HOME/miniconda3
~/miniconda3/bin/conda init bash
source ~/.bashrc
conda create -n adk310 python=3.10 -y
conda activate adk310
cd ~/adk-mcp
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 📚 Documentation & References

- **Agent Configuration:** See `local_mcp/agent.py` for agent setup with session management
- **MCP Server Tools:** See `local_mcp/server.py` for all 26 tool implementations including session tools
- **Session Management:** See `local_mcp/session_context_simple.py` for simplified 3-table SQLite schema
- **Agent Prompt:** See `local_mcp/prompt.py` for comprehensive instructions including session management
- **Custom Evaluation:** See `eval.py` for custom evaluation script
- **Test Configuration:** See `test_config.json` for evaluation configuration

---

## 🎯 Key Features

- **26 Advanced MCP Tools** for comprehensive HTCondor management and session control
- **Google ADK Context Integration** with persistent session management and cross-conversation memory
- **Simplified 3-Table SQLite Schema** for efficient session and context storage
- **Intelligent Agent** with context-aware responses and session continuity
- **Custom Evaluation Framework** with comprehensive test cases
- **Advanced Monitoring** including resource usage, system load, and analytics
- **Flexible Reporting** with time-based analysis and data export
- **Production Ready** with error handling and logging
- **ADK Compatible** for integration with official evaluation frameworks

---

**For local development, HTCondor is not required. For production use, deploy to ATLAS Facility with HTCondor available.**
