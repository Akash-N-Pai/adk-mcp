# ADK Agent MCP Server

This project demonstrates an Agent Development Kit (ADK) agent that interacts with the ATLAS Facility via HTCondor using a local Model Context Protocol (MCP) server. The MCP server exposes tools to query, monitor, and submit jobs to the facility with session state management for context-aware responses, and the agent uses these tools to fulfill user requests.

## 🚀 Quick Start

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Clone and setup
git clone <repository-url>
cd adk-mcp
make install-dev

# Set up API key
echo "GOOGLE_API_KEY=your_gemini_api_key_here" > .env

# Run tests
make test

# Start agent
make run-agent
```

## 📁 Project Structure

```
adk-mcp/
├── local_mcp/
│   ├── agent.py             # The ADK agent for HTCondor/ATLAS Facility
│   ├── server.py            # The MCP server exposing HTCondor tools with session state
│   ├── prompt.py            # Prompt instructions for the agent
│   └── __init__.py
├── tests/                   # Test suite
├── evaluation/
│   └── evaluation.py        # Evaluation framework and scenarios
├── requirements.txt         # Production dependencies
├── requirements-dev.txt     # Development dependencies
├── Makefile                # Development commands
└── .env                    # Environment variables (create this)
```

## 🛠️ Available Tools

The MCP server exposes these tools for the ADK agent:

- **`list_jobs(owner: str = None, status: str = None) -> dict`**: Lists jobs in the queue, optionally filtered by owner or status. Returns only the first 10 jobs and includes total_jobs count. Updates session state with recent jobs and query time.
- **`get_job_status(cluster_id: str) -> dict`**: Retrieves the status/details for a specific job by cluster ID. Tracks job queries in session history.
- **`submit_job(submit_description: dict) -> dict`**: Submits a new job to HTCondor. Records job submission in session history.
- **`get_session_state() -> dict`**: Retrieves current session information for context-aware responses.

## 💬 Demo Conversation

**User:** `List all jobs in the queue.`

**Agent:**
```json
{
  "success": true,
  "jobs": [
    {"ClusterId": 123, "JobStatus": 2, "Owner": "alice", ...},
    {"ClusterId": 124, "JobStatus": 1, "Owner": "bob", ...}
  ],
  "session_info": {
    "query_time": 1640995200.0,
    "total_jobs": 2
  }
}
```

**User:** `What jobs did I look at recently?`

**Agent:**
```json
{
  "success": true,
  "session_state": {
    "recent_jobs_count": 2,
    "job_history_count": 0,
    "last_query_time": 1640995200.0,
    "active_filters": {},
    "recent_job_statuses": [2, 1]
  }
}
```

## 🔄 Session State Management

The MCP server maintains session state for context-aware responses:

### **Tracked Information:**
- **Recent Jobs**: List of jobs from the most recent query
- **Job History**: Record of job status queries and submissions
- **Query Times**: Timestamps of recent operations
- **Active Filters**: Currently applied filters (e.g., owner)

### **Example Session-Aware Interactions:**
- "What jobs did I look at recently?"
- "Show me the status of the job I just submitted"
- "List jobs for the same owner as before"
- "What's my recent job activity?"

## 🧪 Testing & Evaluation

```bash
# Run all tests
make test

# Run evaluation scenarios
python -m evaluation.evaluation --category job_listing
python -m evaluation.evaluation --full
```

The evaluation framework includes realistic scenarios for:
- Job listing and filtering
- Job status queries
- Job submission workflows
- Session state management
- Error handling

## 🔧 Development

```bash
# Code quality
make format
make lint

# Full development cycle
make full-cycle
```

## 🐛 Troubleshooting

### Common Issues

**`No module named 'htcondor'`**:
- Make sure you are running on a system with HTCondor and the Python bindings installed.
- If running on a facility login node, these are usually pre-installed.

**Session state not persisting**:
- Session state is currently in-memory only and resets when the server restarts.
- For persistent state, consider implementing database storage or file-based persistence.

**Python version issues on ATLAS**:
- The default Python on ATLAS is too old for `mcp` or `google-adk`.
- Install Python 3.10+ locally via Miniconda:

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

## 📚 Documentation

- [Evaluation Framework](evaluation/evaluation.py) - Simplified evaluation scenarios and runner

---

**For local development, no HTCondor required. For production use, deploy to ATLAS Facility.**
