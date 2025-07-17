# ADK Agent MCP Server

This project demonstrates an Agent Development Kit (ADK) agent that interacts with the ATLAS Facility via HTCondor using a local Model Context Protocol (MCP) server. The MCP server exposes tools to query, monitor, and submit jobs to the facility, and the agent uses these tools to fulfill user requests with context-aware, session-based responses.

---

## 🚀 Quick Start

```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Clone and setup
git clone <repository-url>
cd adk-mcp
make install-dev

# Set up API key and (optionally) MCP server host/port
echo "GOOGLE_API_KEY=your_gemini_api_key_here" > .env
# Optionally set MCP_SERVER_HOST and MCP_SERVER_PORT in .env

# Run tests
make test

# Run eval
make eval-full  

# Start agent (web interface)
make run-agent
```

---

## 📁 Project Structure

```
adk-mcp/
├── local_mcp/
│   ├── agent.py               # The ADK agent for HTCondor/ATLAS Facility
│   ├── server.py              # The MCP server exposing HTCondor tools
│   ├── prompt.py              # Prompt instructions for the agent
│   ├── __init__.py
│   └── mcp_server_activity.log # Server activity log (auto-generated)
├── tests/
│   ├── test_agent_integration.py # Integration tests for agent/server
│   ├── test_mcp_server.py        # Unit tests for MCP server tools
│   └── __init__.py
├── evaluation/
│   ├── evaluation.py          # Evaluation framework and scenarios
│   └── __init__.py
├── requirements.txt           # Production dependencies
├── requirements-dev.txt       # Development dependencies
├── Makefile                   # Development commands
├── .env                       # Environment variables (create this)
└── readme.md                  # Project documentation
```

---

## 🛠️ Available Tools (via MCP Server)

The MCP server exposes these tools for the ADK agent:

- **`list_jobs(owner: str = None, status: str = None, limit: int = 10) -> dict`**: Lists jobs in the queue, optionally filtered by owner or status. Returns only the first `limit` jobs (default 10) and includes `total_jobs` count.
- **`get_job_status(cluster_id: int) -> dict`**: Retrieves the status/details for a specific job by cluster ID.
- **`submit_job(submit_description: dict) -> dict`**: Submits a new job to HTCondor. The description should include at least `executable` and optionally `arguments`, `output`, `error`, `log`, etc.

All tools return a `success` flag and relevant data or error messages.

---

## 🤖 Agent & Prompt Principles

The agent is configured in `local_mcp/agent.py` and uses a prompt (`local_mcp/prompt.py`) that enforces these principles:

- **Prioritize Action:** Use the relevant tool immediately when a user's request implies a job management operation.
- **Smart Defaults:**
    - For `get_job_status`, provide the `cluster_id` if available, or ask for clarification.
    - For `list_jobs`, if `owner` is not specified, list all jobs.
    - For `submit_job`, ask for missing required fields.
- **Minimize Clarification:** Only ask clarifying questions if the user's intent is ambiguous.
- **User-Friendly Output:**
    - For job lists, output a table with headers (ClusterId, ProcId, Status, Owner) and map status codes to human-readable words (e.g., 1=Idle, 2=Running, 5=Held, etc.).
    - For single job status, provide a summary of key fields in plain language.
    - For job submission, confirm the action and show the new job's ID.
- **Error Handling:** If a tool fails, explain the error in simple terms and suggest next steps.

**Example Interactions:**

```
User: Show me all running jobs for user alice.
Agent: (calls list_jobs with owner="alice", status="running")
Output:
Jobs for user alice (Running):
| ClusterId | ProcId | Status  | Owner  |
|-----------|--------|---------|--------|
| 1234567   | 0      | Running | alice  |
| 1234568   | 0      | Running | alice  |
Total jobs shown: 2 (out of 10 max displayed)

User: What's the status of job 1234567?
Agent: (calls get_job_status with cluster_id=1234567)
Output:
Job 1234567 status:
- Owner: alice
- Status: Running
- ProcId: 0
- ...

User: Submit a job with this description...
Agent: (calls submit_job with provided description)
Output:
Job submitted successfully! New ClusterId: 2345678
```

---

## 🧠 Architecture Overview

- **Agent (`local_mcp/agent.py`):**
    - Loads environment variables from `.env` (requires `GOOGLE_API_KEY`).
    - Launches the MCP server (`local_mcp/server.py`) as a subprocess using stdio for communication.
    - Uses the Gemini model and a custom prompt for job management.
- **MCP Server (`local_mcp/server.py`):**
    - Exposes tools for job listing, status, and submission via HTCondor.
    - Handles requests from the agent and returns JSON-serializable results.
    - Logs activity to `mcp_server_activity.log`.
    - Can be run as a standalone process if needed.

---

## 🧪 Testing & Evaluation

### **Testing**

```bash
make test            # Run all tests
make test-unit       # Run unit tests only
make test-integration # Run integration tests only
make test-cov        # Run tests with coverage report
```

- **Test files:**
    - `tests/test_agent_integration.py`: Integration tests for agent/server communication and configuration.
    - `tests/test_mcp_server.py`: Unit tests for MCP server tool logic and error handling.

### **Evaluation Framework**

```bash
make eval-full                # Run full evaluation suite
python -m evaluation.evaluation --category job_listing
python -m evaluation.evaluation --full
python -m evaluation.evaluation --list   # List all scenarios
```

- **Scenarios:**
    - Job listing and filtering
    - Job status queries
    - Job submission workflows
    - Error handling
- **Categories:** `job_listing`, `job_status`, `job_submission`, `error_handling`
- **Difficulties:** `easy`, `medium`, etc.

---

## 🛠️ Development Workflow

```bash
make format         # Format code with black
make lint           # Run linting checks (flake8, mypy)
make full-cycle     # Clean, install, format, lint, test, evaluate
make clean          # Remove build/test artifacts
```

---

## ⚙️ Environment Variables

- `GOOGLE_API_KEY` (required): API key for Gemini model.
- `MCP_SERVER_HOST` (optional): Host for MCP server (default: localhost).
- `MCP_SERVER_PORT` (optional): Port for MCP server (default: 8001).

Create a `.env` file in the project root with at least:
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
- **Development:** (see `requirements-dev.txt`)
    - `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-mock`, `black`, `flake8`, `mypy`, `pre-commit`

---

## 🐛 Troubleshooting

### Common Issues

- **`No module named 'htcondor'`**:
    - Make sure you are running on a system with HTCondor and the Python bindings installed.
    - If running on a facility login node, these are usually pre-installed.
- **Session state not persisting**:
    - Session state is currently in-memory only and resets when the server restarts.
    - For persistent state, consider implementing database or file-based storage.
- **Python version issues on ATLAS**:
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

---

## 📚 Documentation & References

- **Prompt & Principles:** See `local_mcp/prompt.py` for agent instructions and example interactions.
- **Evaluation Framework:** See `evaluation/evaluation.py` for scenario structure and CLI options.
- **Server Tools:** See `local_mcp/server.py` for tool implementations and status code mapping.

---

**For local development, HTCondor is not required. For production use, deploy to ATLAS Facility with HTCondor available.**
