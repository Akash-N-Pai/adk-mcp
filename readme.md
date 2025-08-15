# HTCondor MCP Agent for ATLAS Facility

A comprehensive Agent Development Kit (ADK) agent that provides advanced HTCondor management capabilities for the ATLAS Facility. The agent uses a local Model Context Protocol (MCP) server to interact with HTCondor, offering job management, resource monitoring, reporting, and **advanced analytics** functionality with **Google ADK Context integration** for persistent session management and cross-conversation memory.

---

## 🚀 Quick Start

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Clone and setup
git clone https://github.com/maniaclab/adk-mcp.git
cd adk-mcp
pip install -r requirements.txt

# Set up API key
echo "GOOGLE_API_KEY=your_gemini_api_key_here" > .env

# Run tests
python -m pytest

# Run evaluation (must have the coversation in jason format)
python eval.py

# Start agent (web interface)
cd adk-mcp  
adk web

# Start agent (web interface)
cd adk-mcp  
adk run local_mcp
```

---

## 📁 Project Structure

```
adk-mcp/
├── local_mcp/
│   ├── agent.py               # ADK agent with session management and context
│   ├── server.py              # MCP server with 20+ tools including advanced analytics
│   ├── htcondor_dataframe.py  # Global DataFrame for job data management
│   ├── session_context_simple.py # Simplified 3-table SQLite session management
│   ├── prompt.py              # Comprehensive prompt with session instructions
│   ├── __init__.py
│   ├── sessions_simple.db     # Session database (auto-generated)
│   └── session_simple.db      # Session database (auto-generated)
├── requirements.txt           # Production dependencies
├── .env                       # Environment variables (create this)
└── readme.md                  # Project documentation
```

---

## 🛠️ Available Tools (20+ MCP Tools)

The MCP server exposes comprehensive tools for HTCondor management, session management, and **advanced analytics**:

### Basic Job Management
- **`list_jobs(owner, status, limit)`**: List jobs with filtering options using global DataFrame
- **`get_job_status(cluster_id)`**: Get detailed status for specific job using global DataFrame
- **`submit_job(submit_description)`**: Submit new jobs to HTCondor

### Advanced Job Information
- **`get_job_history(cluster_id, limit)`**: Get job execution history and events using global DataFrame

### Reporting and Analytics
- **`generate_job_report(owner, time_range)`**: Generate comprehensive job reports using global DataFrame
- **`get_utilization_stats(time_range)`**: Get resource utilization statistics using global DataFrame
- **`export_job_data(format, filters)`**: Export job data (JSON/CSV/Summary) using global DataFrame

### **Advanced Analytics Tools** 🆕
- **`generate_advanced_job_report(owner, time_range, report_type, output_format)`**: 
  - Multi-format comprehensive reports (JSON, CSV, text, summary)
  - Performance insights and failure analysis
  - Resource efficiency metrics and temporal analysis
  - Owner-specific analytics and success rate calculations

- **`generate_queue_wait_time_histogram(time_range, bin_count, owner, status_filter)`**:
  - Queue wait time analysis with customizable bins
  - Statistical analysis (mean, median, percentiles)
  - Sample job details with wait time breakdowns

- **`analyze_job_failures(time_range, owner, failure_type)`**:
  - Detailed failure pattern analysis
  - Exit code distribution and failure trends
  - Time-based failure clustering
  - Failure rate calculations and recommendations

- **`generate_user_performance_dashboard(owner, time_range, metrics)`**:
  - User-specific performance metrics
  - Resource utilization analysis
  - Success rate tracking and efficiency scores
  - Comparative analysis across users

- **`analyze_job_efficiency(time_range, owner, efficiency_metric)`**:
  - Resource utilization efficiency analysis
  - CPU and memory efficiency scoring
  - Efficiency distribution and optimization recommendations
  - Performance benchmarking

- **`advanced_job_search(criteria, filters, limit)`**:
  - Multi-criteria job search with complex filters
  - Resource usage filtering and status-based search
  - Time range filtering and owner filtering
  - Detailed job information retrieval

### Global DataFrame Management 🆕
- **`get_dataframe_status()`**: Get current status of global DataFrame
- **`refresh_dataframe()`**: Force refresh of global DataFrame data

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

All tools return structured JSON responses with success flags and relevant data.

---

## 🤖 Agent Capabilities

The agent provides intelligent HTCondor management with **Google ADK Context integration** and these capabilities:

### Job Management
- **Smart Filtering**: Filter jobs by owner, status, time ranges using global DataFrame
- **Batch Operations**: Handle multiple jobs efficiently
- **Status Tracking**: Monitor job states and transitions
- **Resource Monitoring**: Track CPU, memory, and disk usage

### **Advanced Analytics** 🆕
- **Comprehensive Reporting**: Multi-format reports with performance insights
- **Failure Analysis**: Detailed failure pattern analysis and recommendations
- **Resource Efficiency**: CPU and memory efficiency scoring and optimization
- **User Performance**: User-specific performance dashboards and metrics
- **Queue Analysis**: Wait time histograms and statistical analysis
- **Advanced Search**: Multi-criteria job search with complex filters

### System Monitoring
- **Global DataFrame**: Centralized job data management with caching
- **Resource Analytics**: Analyze system utilization and performance
- **Capacity Planning**: Understand available resources
- **Data Persistence**: Maintain data across tool calls and sessions

### Advanced Features
- **Job History**: Track job lifecycle and state changes
- **Requirements Analysis**: Understand job constraints and needs
- **Environment Management**: Monitor job execution environments
- **Error Handling**: Robust error handling and recovery
- **JSON Serialization**: Proper handling of pandas Timestamp and numpy types

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

### Advanced Analytics
```
User: Generate an advanced job report for the last 7 days with comprehensive analytics.
Agent: [Calls generate_advanced_job_report with time_range="7d", report_type="comprehensive"]
Output:
=== ADVANCED JOB REPORT ===
Generated: 2025-01-27T10:30:00
Time Range: 7d
Report Type: comprehensive

--- SUMMARY ---
Total Jobs: 6289
Success Rate: 85.2% (of final jobs)
Active Jobs: 516 (8.2%)
Failure Rate: 14.8%
Completion Rate: 22.2%
Final Jobs: 4230 (completed + failed)
Total CPU Time: 45230.5
Total Memory Usage: 13061376.0 MB
Average Completion Time: 2847.3 seconds

--- STATUS DISTRIBUTION ---
Status 1 (Idle): 1505 jobs (23.9%)
Status 2 (Running): 516 jobs (8.2%)
Status 4 (Completed): 1395 jobs (22.2%)
Status 3 (Removed): 2840 jobs (45.2%)

--- OWNER ANALYSIS ---
Owner: akashvnp
  Total Jobs: 4230
  Success Rate: 85.2%
  Total CPU Time: 45230.5

--- PERFORMANCE INSIGHTS ---
• Low resource utilization detected - consider optimizing job requirements
• Most common failure reason: Exit code 1 (2840 occurrences)
```

### Queue Wait Time Analysis
```
User: Show me a histogram of queue wait times for the last 30 days.
Agent: [Calls generate_queue_wait_time_histogram with time_range="30d"]
Output:
Queue Wait Time Histogram (Last 30 days):
Total Jobs Analyzed: 7699
Jobs with Wait Times: 4230

Statistics:
- Mean Wait Time: 2847.3 seconds
- Median Wait Time: 1800.0 seconds
- 95th Percentile: 7200.0 seconds
- Maximum Wait Time: 86400.0 seconds

Histogram Bins:
0-3600s: 2840 jobs (67.1%)
3600-7200s: 847 jobs (20.0%)
7200-10800s: 423 jobs (10.0%)
10800-14400s: 120 jobs (2.8%)
```

### Failure Analysis
```
User: Analyze job failures for user akashvnp in the last 24 hours.
Agent: [Calls analyze_job_failures with time_range="24h", owner="akashvnp"]
Output:
Job Failure Analysis for akashvnp (Last 24 hours):
Total Jobs: 2840
Failed Jobs: 2840
Failure Rate: 100.0%

Failure Distribution:
- Exit Code 1: 2840 jobs (100.0%)
- Exit Code 137: 0 jobs (0.0%)
- Exit Code 139: 0 jobs (0.0%)

Failure Patterns:
- Most common failure: Exit code 1 (2840 occurrences)
- Peak failure time: 14:00-15:00 (423 failures)
- Average failure time: 2.5 hours after submission

Recommendations:
• Investigate exit code 1 failures - likely application errors
• Check job requirements and resource allocation
• Review job submission scripts for common issues
```

### Session Management
```
User: List all my sessions
Agent: [Calls list_user_sessions()]
Output:
Your Sessions:
| Session ID | Created | Last Activity | Conversations |
|------------|---------|---------------|---------------|
| d07b6c99... | 2025-01-27 | 2025-01-27 | 15 |

User: Continue session d07b6c99-ac10-4656-bb9b-24d64e35b2bc
Agent: [Calls continue_specific_session() and get_session_history()]
Output:
Welcome back! I can see you were working with jobs 1234567 and 1234568 earlier...
```

---

## 🧪 Testing & Evaluation

### Comprehensive Testing
```bash
python -m pytest                    # Run all tests
python -m pytest tests/             # Run unit tests only
python -m pytest tests/ -v          # Run with verbose output
python -m pytest tests/ --cov       # Run with coverage report
```

### ADK Evaluation Framework
```bash
python eval.py                      # Run ADK evaluation
python eval.py --verbose            # Run with verbose output
python eval.py --custom-path        # Run with custom paths
```

**Evaluation Coverage:**
- **30+ Test Cases** covering 7 categories
- **20+ MCP Tools** comprehensively tested including advanced analytics
- **Complex Scenarios** including multi-tool interactions
- **Error Handling** and edge cases
- **Agent Integration** testing
- **Session Management** testing
- **Global DataFrame** testing

**Test Categories:**
1. Basic Job Management
2. Advanced Job Information
3. Reporting and Analytics
4. Advanced Analytics Tools
5. Global DataFrame Management
6. Complex Queries
7. Error Handling

---

## 🛠️ Development Workflow

```bash
black local_mcp/    # Format code with black
flake8 local_mcp/   # Run linting checks
mypy local_mcp/     # Run type checking
python -m pytest    # Run tests
python eval.py      # Run evaluation
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
    - `google-adk==1.0.0`
    - `mcp==1.9.1`
    - `deprecated==1.2.13`
    - `htcondor==24.9.2`
    - `pandas==2.0.3`
    - `numpy==1.24.3`

---

## 🐛 Troubleshooting

### Common Issues

- **`No module named 'htcondor'`**:
    - Ensure HTCondor Python bindings are installed
    - On ATLAS Facility, these are usually pre-installed
- **Agent not responding**:
    - Verify `GOOGLE_API_KEY` is set correctly
    - Check agent logs for connection issues
- **JSON serialization errors**:
    - All tools now properly handle pandas Timestamp and numpy types
    - Global DataFrame ensures consistent data handling
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
- **MCP Server Tools:** See `local_mcp/server.py` for all 20+ tool implementations including advanced analytics
- **Global DataFrame:** See `local_mcp/htcondor_dataframe.py` for centralized job data management
- **Session Management:** See `local_mcp/session_context_simple.py` for simplified 3-table SQLite schema
- **Agent Prompt:** See `local_mcp/prompt.py` for comprehensive instructions including session management

---

## 🎯 Key Features

- **20+ Advanced MCP Tools** for comprehensive HTCondor management, session control, and analytics
- **6 New Advanced Analytics Tools** with comprehensive reporting and analysis capabilities
- **Global DataFrame Integration** for centralized job data management and improved performance
- **Google ADK Context Integration** with persistent session management and cross-conversation memory
- **Simplified 3-Table SQLite Schema** for efficient session and context storage
- **Intelligent Agent** with context-aware responses and session continuity
- **Robust Testing** with comprehensive test cases and ADK evaluation framework
- **Advanced Monitoring** including resource usage, system load, and analytics
- **Flexible Reporting** with time-based analysis and data export
- **Production Ready** with error handling, logging, and JSON serialization
- **ADK Compatible** for integration with official evaluation frameworks

---

## 🔄 Recent Updates

### **Advanced Analytics Tools Added:**
- `generate_advanced_job_report` - Multi-format comprehensive reports
- `generate_queue_wait_time_histogram` - Wait time analysis with statistics
- `analyze_job_failures` - Failure pattern analysis and recommendations
- `generate_user_performance_dashboard` - User-specific performance metrics
- `analyze_job_efficiency` - Resource efficiency analysis and optimization
- `advanced_job_search` - Multi-criteria job search with complex filters

### **Global DataFrame Integration:**
- All tools now use centralized global DataFrame for improved performance
- Automatic data persistence across tool calls and sessions
- Thread-safe global instance with proper locking
- Enhanced caching and data consistency

### **Technical Improvements:**
- Fixed JSON serialization issues (pandas Timestamp, NaT objects)
- Enhanced data type handling and conversion
- Improved error handling and logging
- Better performance and data consistency

---

**For local development, HTCondor is not required. For production use, deploy to ATLAS Facility with HTCondor available.**
