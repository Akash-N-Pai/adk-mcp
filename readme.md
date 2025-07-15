# ADK Agent MCP Server

This project demonstrates an Agent Development Kit (ADK) agent that interacts with the ATLAS Facility via HTCondor using a local Model Context Protocol (MCP) server. The MCP server exposes tools to query, monitor, and submit jobs to the facility, and the agent uses these tools to fulfill user requests.

## Project Structure

```
adk-mcp/
├── local_mcp/
│   ├── agent.py             # The ADK agent for the local SQLite DB
│   ├── server.py            # The MCP server exposing database tools
│   ├── prompt.py            # Prompt instructions for the agent
│   └── __init__.py
├── .env                   # For GOOGLE_API_KEY (ensure it's in .gitignore if repo is public)
├── requirements.txt       # Python dependencies
├── .gitignore             # Git ignore rules
└── readme.md              # This file
```

## Setup Instructions

### 1. Prerequisites
- Python 3.10 or newer
- Access to a terminal or command prompt

### 2. Create and Activate Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies.

```bash
python3 -m venv .venv
```

Activate the virtual environment:

On macOS/Linux:
```bash
source .venv/bin/activate
```

On Windows:
```bash
.venv\Scripts\activate
```

### 3. Install Dependencies

Install all required Python packages using pip:

```bash
pip install -r requirements.txt
```

### 4. Set Up Gemini API Key (for the ADK Agent)


  Set the API key as an environment variable. Create a `.env` file

    ```env
    GOOGLE_API_KEY=your_gemini_api_key_here
    ```

## Running the Agent and MCP Server

To run the agent:

1.  Ensure your virtual environment is active and you are in the root directory `adk-mcp`.
2.  Execute the agent script:

    ```bash
    adk web
    ```

This will:
- Start the `agent.py` script.
- The agent, upon initializing the `MCPToolset`, will execute the `python3 local_mcp/server.py` command.
- The `server.py` (MCP server) will start and listen for tool calls from the agent via stdio.
- The agent will then be ready to process your instructions (which you would typically provide in a client application or test environment that uses this agent).

You should see log output from both the agent (if any) and the MCP server (in `local_mcp/mcp_server_activity.log`, and potentially to the console if you uncomment the stream handler in `server.py`).

## Demo Conversation

Below is an example of how you might interact with the agent (via a client or test harness) to use the local MCP tools:

**User:**
```
List all jobs in the queue.
```
**Agent:**
```
{
  "success": true,
  "jobs": [
    {"ClusterId": 123, "JobStatus": 2, "Owner": "alice", ...},
    {"ClusterId": 124, "JobStatus": 1, "Owner": "bob", ...}
  ]
}
```

**User:**
```
Get the status of job 123.
```
**Agent:**
```
{
  "success": true,
  "job": {"ClusterId": 123, "JobStatus": 2, "Owner": "alice", ...}
}
```

**User:**
```
Submit a new job with the following description: {"executable": "/bin/sleep", "arguments": "60"}
```
**Agent:**
```
{
  "success": true,
  "cluster_id": 125
}
```

## Available Tools (Exposed by MCP Server)

The `local_mcp/server.py` exposes the following tools for the ADK agent to use:

- **`list_jobs(owner: str = None) -> dict`**: Lists all jobs in the queue, optionally filtered by owner.
- **`get_job_status(cluster_id: int) -> dict`**: Retrieves the status/details for a specific job.
- **`submit_job(submit_description: dict) -> dict`**: Submits a new job to HTCondor.

## Troubleshooting

* **`No module named 'htcondor'`**:
    * Make sure you are running on a system with HTCondor and the Python bindings installed.
    * If running on a facility login node, these are usually pre-installed.

* **`Could not find a version that satisfies the requirement mcp==1.9.1`** or **`Requires-Python >=3.10`**:
    * The default Python on ATLAS is too old for `mcp` or `google-adk`.
    * Run the following to install Python 3.10+ locally via Miniconda:

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

    * These changes only affect your user account and are safe for use on ATLAS.


## Acknowledgements

This project was structured and the prompts were designed with the help of AI assistance to ensure clarity, efficiency, and best practices.
